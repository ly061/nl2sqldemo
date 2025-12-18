"""
测试用例生成简化多 Agent 系统
只包含：Supervisor、测试用例生成专家、测试用例评审专家
"""
import sys
import json
from pathlib import Path
from typing import TypedDict, Annotated, Literal
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
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


# ==================== 创建各个专家 Agent ====================

def create_test_case_generation_agent():
    """创建测试用例生成专家 Agent"""
    return create_agent(
        model=llm,
        tools=[save_test_cases],
        system_prompt="""你是一个专业的测试用例生成专家。你的任务是：
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
    )


def create_test_case_review_agent():
    """创建测试用例评审专家 Agent"""
    return create_agent(
        model=llm,
        tools=[get_test_cases],
        system_prompt="""你是一个专业的测试用例评审专家。你的任务是：
1. 使用 get_test_cases 工具获取测试用例
2. 对测试用例进行全面评审，从以下维度打分（0-100分）：
   - coverage_score: 覆盖率（是否充分覆盖需求的各种场景）
   - executability_score: 可执行性（步骤是否清晰、可执行）
   - clarity_score: 无歧义性（预期结果是否明确）
3. 总分 = (coverage_score + executability_score + clarity_score) / 3
4. 如果总分 < 80，提供具体的优化建议
5. 输出JSON格式的评审结果：
   {{
     "score": 总分,
     "coverage_score": 覆盖率评分,
     "executability_score": 可执行性评分,
     "clarity_score": 无歧义性评分,
     "suggestions": ["优化建议1", "优化建议2"],
     "is_passed": true/false (score >= 80)
   }}

评审要严格、客观，确保测试用例质量。"""
    )


# ==================== 状态定义 ====================

class AgentState(TypedDict):
    """Agent 状态"""
    messages: Annotated[list, add_messages]
    original_requirement: str  # 原始需求文档
    test_cases: list[dict]  # 测试用例列表（JSON格式）
    review_result: dict | None  # 评审结果（JSON格式）
    iteration_count: int  # 迭代次数
    current_agent: str  # 当前执行的 Agent 名称
    optimization_suggestions: list[str]  # 优化建议
    final_output: str  # 最终输出


# ==================== Agent 节点函数 ====================

def test_case_generation_agent_node(state: AgentState) -> AgentState:
    """测试用例生成专家 Agent 节点"""
    log.info("测试用例生成专家 Agent 开始工作...")
    
    # 设置全局状态，供工具函数使用
    set_global_state(state)
    
    agent = create_test_case_generation_agent()
    original_requirement = state.get("original_requirement", "")
    optimization_suggestions = state.get("optimization_suggestions", [])
    
    try:
        # 构建提示，包含优化建议（如果有）
        optimization_hint = ""
        if optimization_suggestions:
            optimization_hint = f"\n\n请特别注意以下优化建议：\n" + "\n".join([
                f"- {suggestion}" for suggestion in optimization_suggestions
            ])
        
        messages = [HumanMessage(content=f"请根据以下需求文档生成测试用例：\n\n{original_requirement}{optimization_hint}")]
        response = agent.invoke({"messages": messages})
        
        # 解析响应，提取测试用例
        last_message = response.get("messages", [])[-1] if isinstance(response, dict) else response[-1] if isinstance(response, list) else None
        
        if last_message and hasattr(last_message, 'content'):
            content = last_message.content
            try:
                import re
                # 查找 JSON 数组
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    test_cases_data = json.loads(json_match.group())
                    if isinstance(test_cases_data, list):
                        for idx, tc in enumerate(test_cases_data):
                            tc.setdefault("test_case_id", f"TC_{idx+1:03d}")
                        state["test_cases"] = test_cases_data
            except Exception as e:
                log.warning(f"解析测试用例失败: {e}")
        
        # 从全局状态更新本地状态（工具函数可能已经更新了全局状态）
        updated_state = get_global_state()
        if "test_cases" in updated_state and updated_state["test_cases"]:
            state["test_cases"] = updated_state["test_cases"]
        
        # 确保测试用例已设置
        if not state.get("test_cases"):
            # 如果解析失败，创建默认测试用例
            state["test_cases"] = [{
                "test_case_id": "TC_001",
                "test_type": "功能测试",
                "test_description": "基本功能测试",
                "test_steps": ["步骤1: 准备测试环境", "步骤2: 执行测试", "步骤3: 验证结果"],
                "expected_result": "测试通过",
                "priority": "中",
                "preconditions": ""
            }]
        
        state["current_agent"] = "test_case_generation_agent"
        state["optimization_suggestions"] = []  # 清空优化建议（已应用）
        state["messages"].append(AIMessage(content=f"测试用例生成完成：共生成 {len(state.get('test_cases', []))} 个测试用例"))
        log.info(f"测试用例生成专家 Agent 完成工作：共生成 {len(state.get('test_cases', []))} 个测试用例")
        
    except Exception as e:
        log.error(f"测试用例生成 Agent 执行失败: {e}")
        # 确保即使异常也设置测试用例
        if not state.get("test_cases"):
            state["test_cases"] = [{
                "test_case_id": "TC_001",
                "test_type": "功能测试",
                "test_description": "基本功能测试",
                "test_steps": ["步骤1: 准备测试环境", "步骤2: 执行测试", "步骤3: 验证结果"],
                "expected_result": "测试通过",
                "priority": "中",
                "preconditions": ""
            }]
        state["current_agent"] = "test_case_generation_agent"
        state["messages"].append(AIMessage(content=f"测试用例生成失败: {str(e)}"))
    
    return state


def test_case_review_agent_node(state: AgentState) -> AgentState:
    """测试用例评审专家 Agent 节点"""
    log.info("测试用例评审专家 Agent 开始工作...")
    
    # 设置全局状态，供工具函数使用
    set_global_state(state)
    
    agent = create_test_case_review_agent()
    test_cases = state.get("test_cases", [])
    original_requirement = state.get("original_requirement", "")
    
    if not test_cases:
        state["messages"].append(AIMessage(content="错误：没有测试用例，无法进行评审"))
        return state
    
    try:
        # 构建评审上下文
        review_context = {
            "original_requirement": original_requirement,
            "test_cases": test_cases
        }
        
        messages = [HumanMessage(content=f"请评审以下测试用例：\n\n原始需求：\n{original_requirement}\n\n测试用例：\n{json.dumps(test_cases, ensure_ascii=False, indent=2)}")]
        response = agent.invoke({"messages": messages})
        
        # 解析响应，提取评审结果
        last_message = response.get("messages", [])[-1] if isinstance(response, dict) else response[-1] if isinstance(response, list) else None
        
        if last_message and hasattr(last_message, 'content'):
            content = last_message.content
            try:
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    review_data = json.loads(json_match.group())
                    # 确保字段完整
                    if "score" not in review_data:
                        scores = review_data.get("scores", {})
                        total = review_data.get("total_score", 0)
                        if not total and scores:
                            total = (scores.get("coverage", 0) + scores.get("executability", 0) + scores.get("clarity", 0)) / 3
                        review_data["score"] = int(total)
                        review_data["coverage_score"] = scores.get("coverage", 0)
                        review_data["executability_score"] = scores.get("executability", 0)
                        review_data["clarity_score"] = scores.get("clarity", 0)
                        review_data["is_passed"] = review_data["score"] >= 80
                        
                        # 提取优化建议
                        suggestions = []
                        opt_suggestions = review_data.get("optimization_suggestions", [])
                        for opt in opt_suggestions:
                            if isinstance(opt, dict):
                                if "suggestion" in opt:
                                    suggestions.append(opt["suggestion"])
                                elif "suggestions" in opt:
                                    suggestions.extend(opt["suggestions"])
                            elif isinstance(opt, str):
                                suggestions.append(opt)
                        review_data["suggestions"] = suggestions
                    
                    state["review_result"] = review_data
                    
                    # 如果未通过，保存优化建议
                    if not review_data.get("is_passed", False):
                        state["optimization_suggestions"] = review_data.get("suggestions", [])
                        # 增加迭代次数
                        state["iteration_count"] = state.get("iteration_count", 0) + 1
            except Exception as e:
                log.error(f"解析评审结果失败: {e}")
                # 创建默认评审结果
                state["review_result"] = {
                    "score": 60,
                    "coverage_score": 60,
                    "executability_score": 60,
                    "clarity_score": 60,
                    "suggestions": ["评审过程出现错误，请检查测试用例"],
                    "is_passed": False
                }
        
        # 确保评审结果已设置
        if "review_result" not in state or state["review_result"] is None:
            state["review_result"] = {
                "score": 60,
                "coverage_score": 60,
                "executability_score": 60,
                "clarity_score": 60,
                "suggestions": ["评审过程出现错误，请检查测试用例"],
                "is_passed": False
            }
        
        state["current_agent"] = "test_case_review_agent"
        review_summary = f"评审完成，得分: {state.get('review_result', {}).get('score', 0)}/100"
        state["messages"].append(AIMessage(content=review_summary))
        log.info(f"测试用例评审专家 Agent 完成工作：得分 {state.get('review_result', {}).get('score', 0)}/100")
        
    except Exception as e:
        log.error(f"测试用例评审 Agent 执行失败: {e}")
        # 确保即使异常也设置评审结果
        state["review_result"] = {
            "score": 60,
            "coverage_score": 60,
            "executability_score": 60,
            "clarity_score": 60,
            "suggestions": [f"评审过程出现错误: {str(e)}"],
            "is_passed": False
        }
        state["current_agent"] = "test_case_review_agent"
        state["messages"].append(AIMessage(content=f"测试用例评审失败: {str(e)}"))
    
    return state


def test_case_generator_node(state: AgentState) -> AgentState:
    """测试用例文档生成节点（非 Agent，直接生成）"""
    log.info("开始生成最终测试用例文档...")
    
    test_cases = state.get("test_cases", [])
    review_result = state.get("review_result")
    original_requirement = state.get("original_requirement", "")
    
    if not test_cases:
        state["messages"].append(AIMessage(content="错误：没有测试用例，无法生成文档"))
        return state
    
    try:
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
        
        final_output = "\n".join(output_lines)
        
        state["final_output"] = final_output
        state["current_agent"] = "test_case_generator"
        
        log.info("测试用例文档生成完成")
        state["messages"].append(AIMessage(content=f"测试用例文档生成完成！共 {len(test_cases)} 个测试用例"))
        
    except Exception as e:
        log.error(f"测试用例文档生成失败: {e}")
        state["messages"].append(AIMessage(content=f"测试用例文档生成失败: {str(e)}"))
    
    return state


# ==================== Supervisor 路由逻辑 ====================

def supervisor_router(state: AgentState) -> Literal[
    "test_case_generation_agent",
    "test_case_review_agent",
    "test_case_generator",
    "end"
]:
    """Supervisor 路由函数：根据当前状态决定下一个 Agent"""
    current_agent = state.get("current_agent", "")
    iteration_count = state.get("iteration_count", 0)
    review_result = state.get("review_result")
    
    # 流程路由逻辑
    if current_agent == "":
        # 初始状态，开始生成测试用例
        return "test_case_generation_agent"
    elif current_agent == "test_case_generation_agent":
        # 测试用例生成完成，进入评审
        return "test_case_review_agent"
    elif current_agent == "test_case_review_agent":
        # 评审完成，检查结果
        if review_result and review_result.get("is_passed", False):
            # 通过评审，进入生成器
            return "test_case_generator"
        elif iteration_count < 3:
            # 未通过且迭代次数未达上限，回退到测试用例生成
            log.info(f"评审未通过（得分: {review_result.get('score', 0) if review_result else 'N/A'}），回退到测试用例生成（迭代次数: {iteration_count}/3）")
            return "test_case_generation_agent"
        else:
            # 迭代次数已达上限，进入生成器（即使未通过）
            log.warning(f"迭代次数已达上限（{iteration_count}），进入生成器")
            return "test_case_generator"
    elif current_agent == "test_case_generator":
        # 生成完成，结束流程
        return "end"
    else:
        # 未知状态，结束流程
        return "end"


def supervisor_node(state: AgentState) -> AgentState:
    """Supervisor 节点：记录路由决策"""
    return state


# ==================== 构建 LangGraph ====================

def create_simple_agent_system():
    """创建简化的多 Agent 系统"""
    
    # 创建状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("test_case_generation_agent", test_case_generation_agent_node)
    workflow.add_node("test_case_review_agent", test_case_review_agent_node)
    workflow.add_node("test_case_generator", test_case_generator_node)
    
    # 设置入口点
    workflow.set_entry_point("supervisor")
    
    # 添加条件边（从 supervisor 到各个 Agent）
    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "test_case_generation_agent": "test_case_generation_agent",
            "test_case_review_agent": "test_case_review_agent",
            "test_case_generator": "test_case_generator",
            "end": END,
        }
    )
    
    # 添加边（各 Agent 完成后回到 supervisor）
    workflow.add_edge("test_case_generation_agent", "supervisor")
    workflow.add_edge("test_case_review_agent", "supervisor")
    workflow.add_edge("test_case_generator", END)
    
    # 编译图
    agent = workflow.compile()
    
    # 尝试生成流程图（可选，如果缺少依赖会跳过）
    try:
        graph = agent.get_graph()
        output_path = Path(__file__).parent.parent.parent / "test_case_simple_agent.png"
        # 使用关键字参数 output_file_path，增加重试次数
        graph.draw_mermaid_png(
            output_file_path=str(output_path),
            max_retries=3,
            retry_delay=2.0
        )
        log.info(f"流程图 PNG 已保存到: {output_path}")
    except Exception as e:
        log.warning(f"无法生成流程图 PNG（可能需要网络连接或本地浏览器）: {e}")
        # 总是生成 Mermaid 文本格式作为备用
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

agent = create_simple_agent_system()


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
    # 初始化状态
    initial_state: AgentState = {
        "messages": [HumanMessage(content=f"请根据以下需求文档生成测试用例：\n\n{requirement_doc}")],
        "original_requirement": requirement_doc,
        "test_cases": [],
        "review_result": None,
        "iteration_count": 0,
        "current_agent": "",
        "optimization_suggestions": [],
        "final_output": "",
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # 运行流程
    final_state = None
    for step in agent.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in step.items():
            log.info(f"节点 {node_name} 执行完成")
            final_state = node_output
    
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
        print(result["final_output"])
    
    if result.get("review_result"):
        review = result["review_result"]
        print(f"\n评审结果：得分 {review.get('score', 0)}/100，{'通过' if review.get('is_passed', False) else '不通过'}")

