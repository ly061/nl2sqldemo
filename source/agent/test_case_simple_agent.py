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

from source.agent.llm import llm
from source.agent.utils.log_utils import MyLogger

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


# ==================== 创建各个专家 Agent ====================

def create_test_case_generation_agent_graph():
    """创建测试用例生成专家 Agent（LangGraph 格式）"""
    system_prompt = """你是一个专业的测试用例生成专家。你的任务是：
1. 仔细分析用户提供的需求文档
2. 直接生成详细的测试用例，包括：
   - test_case_id: 测试用例ID（格式：TC_001, TC_002...）
   - test_type: 测试类型（功能测试/边界测试/异常测试等）
   - test_description: 测试用例描述
   - test_steps: 清晰的测试步骤列表（步骤1、步骤2...）
   - expected_result: 明确的预期结果
   - priority: 优先级（高/中/低）
   - preconditions: 前置条件（可选）
3. 测试用例应该：
   - 覆盖正常场景、边界场景和异常场景
   - 步骤完整、可执行
   - 预期结果明确、无歧义
   - 易于理解和维护
4. 将测试用例以JSON数组格式输出
5. 使用 save_test_cases 工具保存测试用例

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
    
    return create_agent(
        model=llm,
        tools=[save_test_cases],
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
    
    return create_agent(
        model=llm,
        tools=[get_test_cases, save_review_result],
        prompt=system_prompt,
        name="test_case_review_agent",
    )


# ==================== 创建 Supervisor 系统 ====================

def create_supervisor_system():
    """创建 Supervisor 协调的多 Agent 系统"""
    
    # 创建各个专家 Agent
    test_case_generation_agent = create_test_case_generation_agent_graph()
    test_case_review_agent = create_test_case_review_agent_graph()
    
    # 创建 Supervisor
    workflow = create_supervisor(
        agents=[test_case_generation_agent, test_case_review_agent],
        model=llm,
        prompt="""你是一个测试用例生成系统的 Supervisor（协调者）。你的任务是协调两个专家 Agent：

1. test_case_generation_agent（测试用例生成专家）：负责根据需求文档生成测试用例
2. test_case_review_agent（测试用例评审专家）：负责评审测试用例的质量

工作流程：
1. 当用户提供需求文档时，首先调用 test_case_generation_agent 生成测试用例
2. 然后调用 test_case_review_agent 评审测试用例
3. 如果评审通过（分数>=80），任务完成
4. 如果评审不通过（分数<80），将评审建议反馈给 test_case_generation_agent 进行优化，最多迭代3次

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


# ==================== 辅助函数 ====================

def run_test_case_generation(requirement_doc: str, thread_id: str = "default") -> dict:
    """
    运行测试用例生成流程
    
    Args:
        requirement_doc: 原始需求文档
        thread_id: 线程ID（用于状态管理）
    
    Returns:
        包含最终结果的字典
    """
    # 初始化全局状态
    initial_global_state = {
        "original_requirement": requirement_doc,
        "test_cases": [],
        "review_result": None,
        "iteration_count": 0,
        "optimization_suggestions": [],
    }
    set_global_state(initial_global_state)
    
    # 初始化 Supervisor 状态（Supervisor 使用标准的 messages 状态）
    initial_state = {
        "messages": [HumanMessage(content=f"请根据以下需求文档生成测试用例：\n\n{requirement_doc}")],
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # 运行流程
    final_state = None
    for step in agent.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in step.items():
            log.info(f"节点 {node_name} 执行完成")
            final_state = node_output
    
    # 生成最终文档
    if final_state:
        # 从全局状态获取数据
        global_state = get_global_state()
        test_cases = global_state.get("test_cases", [])
        review_result = global_state.get("review_result")
        original_requirement = global_state.get("original_requirement", requirement_doc)
        
        # 从消息中提取数据（备用）
        messages = final_state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'content'):
                content = str(msg.content)
                # 尝试提取测试用例
                if not test_cases and ("test_cases" in content.lower() or "测试用例" in content):
                    try:
                        import re
                        json_match = re.search(r'\[.*\]', content, re.DOTALL)
                        if json_match:
                            test_cases_data = json.loads(json_match.group())
                            if isinstance(test_cases_data, list):
                                test_cases = test_cases_data
                    except:
                        pass
                # 尝试提取评审结果
                if not review_result and ("review_result" in content.lower() or "评审" in content or "score" in content.lower()):
                    try:
                        import re
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            review_data = json.loads(json_match.group())
                            if "score" in review_data:
                                review_result = review_data
                    except:
                        pass
        
        if test_cases:
            # 生成 Markdown 格式的测试用例文档
            output_lines = [
                "# 测试用例文档",
                f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "\n## 1. 需求概述",
                f"\n{original_requirement}",
                "\n## 2. 测试用例",
            ]
            
            # 按测试类型分组
            test_cases_by_type = {}
            for tc in test_cases:
                test_type = tc.get("test_type", "其他")
                if test_type not in test_cases_by_type:
                    test_cases_by_type[test_type] = []
                test_cases_by_type[test_type].append(tc)
            
            # 添加测试用例
            for test_type, cases in test_cases_by_type.items():
                output_lines.append(f"\n### {test_type}")
                for tc in cases:
                    output_lines.extend([
                        f"\n#### 测试用例 {tc.get('test_case_id', 'N/A')}",
                        f"**测试描述**: {tc.get('test_description', 'N/A')}",
                        f"**优先级**: {tc.get('priority', 'N/A')}",
                        f"**前置条件**: {tc.get('preconditions', '无')}",
                        f"\n**测试步骤**:",
                    ])
                    for idx, step in enumerate(tc.get("test_steps", []), 1):
                        output_lines.append(f"{idx}. {step}")
                    output_lines.append(f"\n**预期结果**: {tc.get('expected_result', 'N/A')}")
            
            # 添加评审信息
            if review_result:
                output_lines.extend([
                    "\n## 3. 评审结果",
                    f"**总分**: {review_result.get('score', 0)}/100",
                    f"**覆盖率**: {review_result.get('coverage_score', 0)}/100",
                    f"**可执行性**: {review_result.get('executability_score', 0)}/100",
                    f"**无歧义性**: {review_result.get('clarity_score', 0)}/100",
                    f"**评审结果**: {'通过' if review_result.get('is_passed', False) else '不通过'}",
                ])
                if review_result.get("suggestions"):
                    output_lines.append("\n**优化建议**:")
                    for suggestion in review_result["suggestions"]:
                        output_lines.append(f"- {suggestion}")
            
            # 将最终输出添加到结果中
            result = {
                "messages": final_state.get("messages", []),
                "test_cases": test_cases,
                "review_result": review_result,
                "final_output": "\n".join(output_lines),
            }
            return result
    
    return final_state or {}


if __name__ == "__main__":
    # 示例：运行测试用例生成
    sample_requirement = """
    用户登录功能需求：
    1. 用户可以通过用户名和密码登录系统
    2. 用户名长度为3-20个字符，只能包含字母、数字和下划线
    3. 密码长度为6-20个字符，必须包含至少一个数字和一个字母
    4. 登录失败3次后，账户将被锁定30分钟
    5. 登录成功后，系统应记录登录时间和IP地址
    """
    
    result = run_test_case_generation(sample_requirement, thread_id="test_001")
    
    print("\n" + "="*60)
    print("测试用例生成完成！")
    print("="*60)
    
    if result.get("final_output"):
        print("\n最终输出：")
        print(result["final_output"][:500] + "...")
    
    if result.get("review_result"):
        review = result["review_result"]
        print(f"\n评审结果：得分 {review.get('score', 0)}/100，{'通过' if review.get('is_passed', False) else '不通过'}")
