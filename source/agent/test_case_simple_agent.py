"""
测试用例生成简化多 Agent 系统
使用 LangGraph Supervisor 模式：Supervisor Agent + 测试用例生成专家 Agent + 测试用例评审专家 Agent
参考：https://reference.langchain.com/python/langgraph/supervisor/
"""
import sys
import json
from pathlib import Path
from typing import TypedDict, Annotated
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from source.agent.llm_wrapper import llm
from source.agent.utils.log_utils import MyLogger
from source.agent.tools.tool_word_parser import parse_word_document
from source.agent.tools.tool_excel_generator import generate_excel_from_test_cases

load_dotenv()
log = MyLogger().get_logger()


# ==================== 工具函数 ====================

# 全局状态存储（用于工具函数访问）
_global_state = {}


def set_global_state(state: dict):
    """设置全局状态"""
    global _global_state
    _global_state = state


def get_global_state() -> dict:
    """获取全局状态"""
    return _global_state


@tool
def save_test_cases(test_cases_json: str) -> str:
    """保存测试用例编写结果
    
    Args:
        test_cases_json: JSON格式的测试用例列表
    
    Returns:
        保存结果
    """
    try:
        data = json.loads(test_cases_json)
        state = get_global_state()
        if isinstance(data, dict):
            state["test_cases"] = [data]
        elif isinstance(data, list):
            state["test_cases"] = data
        else:
            state["test_cases"] = [data]
        set_global_state(state)
        count = len(state.get("test_cases", []))
        log.info(f"保存测试用例编写结果: {count} 个测试用例")
        return f"测试用例编写结果已保存: {count} 个测试用例"
    except Exception as e:
        return f"保存失败: {str(e)}"


@tool
def get_test_cases() -> str:
    """获取已保存的测试用例编写结果
    
    Returns:
        JSON格式的测试用例列表
    """
    state = get_global_state()
    test_cases = state.get("test_cases", [])
    return json.dumps(test_cases, ensure_ascii=False)


@tool
def save_review_result(review_result_json: str) -> str:
    """保存评审结果
    
    Args:
        review_result_json: JSON格式的评审结果
    
    Returns:
        保存结果
    """
    try:
        data = json.loads(review_result_json)
        state = get_global_state()
        state["review_result"] = data
        set_global_state(state)
        log.info(f"保存评审结果: 得分 {data.get('score', 0)}/100")
        return f"评审结果已保存: 得分 {data.get('score', 0)}/100"
    except Exception as e:
        return f"保存失败: {str(e)}"


@tool
def get_review_result() -> str:
    """获取已保存的评审结果
    
    Returns:
        JSON格式的评审结果
    """
    state = get_global_state()
    review_result = state.get("review_result", {})
    return json.dumps(review_result, ensure_ascii=False)


# ==================== 创建各个专家 Agent ====================

def create_test_case_generation_agent_graph():
    """创建测试用例生成专家 Agent（LangGraph 格式）"""
    system_prompt = """你是一个专业的测试用例生成专家。你的任务是：
1. 如果用户提供了Word文档路径，首先使用 parse_word_document 工具解析Word文档内容
2. 仔细分析用户提供的需求文档（可能是文本内容或Word文档解析结果）
3. 直接生成详细的测试用例，包括：
   - test_case_id: 测试用例ID（格式：TC_001, TC_002...）
   - test_type: 测试类型（功能测试/边界测试/异常测试等）
   - test_description: 测试用例描述
   - test_steps: 清晰的测试步骤列表（步骤1、步骤2...）
   - expected_result: 明确的预期结果
   - priority: 优先级（高/中/低）
   - preconditions: 前置条件（可选）
4. 测试用例应该：
   - 覆盖正常场景、边界场景和异常场景
   - 步骤完整、可执行
   - 预期结果明确、无歧义
   - 易于理解和维护
5. 将测试用例以JSON数组格式输出
6. 使用 save_test_cases 工具保存测试用例

输出格式示例：
[
  {{
    "test_case_id": "TC_001",
    "test_type": "功能测试",
    "test_description": "正常登录场景",
    "test_steps": ["步骤1: 打开登录页面", "步骤2: 输入正确的用户名和密码", "步骤3: 点击登录按钮"],
    "expected_result": "登录成功，页面跳转到主页",
    "priority": "高",
    "preconditions": "用户已注册"
  }}
]"""
    
    # 使用 create_react_agent 创建 LangGraph agent，并指定名称
    return create_react_agent(
        model=llm,
        tools=[save_test_cases, parse_word_document],
        prompt=system_prompt,
        name="test_case_generation_agent",
    )


def create_test_case_review_agent_graph():
    """创建测试用例评审专家 Agent（LangGraph 格式）"""
    system_prompt = """你是一个专业的测试用例评审专家。你的任务是：
1. 使用 get_test_cases 工具获取测试用例
2. 对测试用例进行全面评审，从以下维度打分（0-100分）：
   - coverage_score: 覆盖率（是否充分覆盖需求的各种场景）
   - executability_score: 可执行性（步骤是否清晰、可执行）
   - clarity_score: 无歧义性（预期结果是否明确）
3. 总分 = (coverage_score + executability_score + clarity_score) / 3
4. 如果总分 < 80，提供具体的优化建议
5. 输出JSON格式的评审结果，并使用 save_review_result 工具保存：
   {{
     "score": 总分,
     "coverage_score": 覆盖率评分,
     "executability_score": 可执行性评分,
     "clarity_score": 无歧义性评分,
     "suggestions": ["优化建议1", "优化建议2"],
     "is_passed": true/false (score >= 80)
   }}

评审要严格、客观，确保测试用例质量。"""
    
    # 使用 create_react_agent 创建 LangGraph agent，并指定名称
    return create_react_agent(
        model=llm,
        tools=[get_test_cases, save_review_result],
        prompt=system_prompt,
        name="test_case_review_agent",
    )


def create_excel_generation_agent_graph():
    """创建Excel生成专家 Agent（LangGraph 格式）"""
    system_prompt = """你是一个Excel文件生成专家。你的任务是：
1. 使用 get_test_cases 工具获取测试用例
2. 使用 get_review_result 工具获取评审结果（如果有）
3. 使用 generate_excel_from_test_cases 工具生成Excel文件
   - 第一个参数：test_cases_json（从get_test_cases获取的JSON字符串）
   - 第二个参数：output_path（可选，如果不提供会自动生成）
   - 第三个参数：review_result_json（从get_review_result获取的JSON字符串，如果有的话）
4. 将测试用例和评审结果导出为格式化的Excel文件，方便用户查看和使用

重要：调用generate_excel_from_test_cases时，需要传递JSON字符串，不要传递对象。"""
    
    # 使用 create_react_agent 创建 LangGraph agent，并指定名称
    return create_react_agent(
        model=llm,
        tools=[get_test_cases, get_review_result, generate_excel_from_test_cases],
        prompt=system_prompt,
        name="excel_generation_agent",
    )


# ==================== 创建 Supervisor 系统 ====================

def create_supervisor_system():
    """创建 Supervisor 协调的多 Agent 系统"""
    
    # 创建各个专家 Agent
    test_case_generation_agent = create_test_case_generation_agent_graph()
    test_case_review_agent = create_test_case_review_agent_graph()
    excel_generation_agent = create_excel_generation_agent_graph()
    
    # 创建 Supervisor
    workflow = create_supervisor(
        agents=[test_case_generation_agent, test_case_review_agent, excel_generation_agent],
        model=llm,
        prompt="""你是一个测试用例生成系统的 Supervisor（协调者）。你的任务是协调三个专家 Agent：

1. test_case_generation_agent（测试用例生成专家）：负责根据需求文档生成测试用例。如果用户提供了Word文档路径，该Agent会自动解析Word文档。
2. test_case_review_agent（测试用例评审专家）：负责评审测试用例的质量
3. excel_generation_agent（Excel生成专家）：负责将测试用例和评审结果导出为Excel文件

工作流程：
1. 当用户提供需求文档（文本或Word文档路径）时，首先调用 test_case_generation_agent 生成测试用例
2. 然后调用 test_case_review_agent 评审测试用例
3. 如果评审通过（分数>=80），调用 excel_generation_agent 生成Excel文件，然后任务完成
4. 如果评审不通过（分数<80），将评审建议反馈给 test_case_generation_agent 进行优化，最多迭代3次
5. 如果迭代3次后仍不通过，也要调用 excel_generation_agent 生成Excel文件（包含当前结果），然后任务完成

请根据当前状态和任务进度，智能地决定调用哪个 Agent 或完成任务。""",
        supervisor_name="supervisor",
    )
    
    # 编译 Supervisor workflow
    agent = workflow.compile()
    
    # 尝试生成流程图
    try:
        graph = agent.get_graph()
        output_path = Path(__file__).parent.parent.parent / "test_case_simple_agent.png"
        graph.draw_mermaid_png(
            output_file_path=str(output_path),
            max_retries=3,
            retry_delay=2.0
        )
        log.info(f"流程图 PNG 已保存到: {output_path}")
    except Exception as e:
        log.warning(f"无法生成流程图 PNG（可能需要网络连接或本地浏览器）: {e}")
        try:
            graph = agent.get_graph()
            mermaid_text = graph.draw_mermaid()
            output_path = Path(__file__).parent.parent.parent / "test_case_simple_agent.mmd"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(mermaid_text)
            log.info(f"Mermaid 流程图文本已保存到: {output_path}")
        except Exception as e2:
            log.warning(f"无法生成 Mermaid 文本: {e2}")
    
    return agent


# ==================== Agent 实例 ====================

agent = create_supervisor_system()


