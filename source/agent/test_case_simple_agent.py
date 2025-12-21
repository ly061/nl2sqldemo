"""
测试用例生成简化多 Agent 系统
使用 LangGraph Supervisor 模式：Supervisor Agent + 测试用例生成专家 Agent + 测试用例评审专家 Agent
参考：https://reference.langchain.com/python/langgraph/supervisor/
"""
import sys
import json
from pathlib import Path
from typing import TypedDict, Annotated, List, Optional, Dict, Any

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain.agents import create_agent
from langgraph_supervisor import create_supervisor
from langgraph.graph.message import add_messages

from source.agent.llm_wrapper import llm
from source.agent.utils.log_utils import MyLogger
from source.agent.tools.tool_word_parser import parse_word_document
from source.agent.tools.tool_excel_generator import generate_excel_from_test_cases

load_dotenv()
log = MyLogger().get_logger()


# ==================== 状态定义 ====================

class ReviewResult(TypedDict):
    """评审结果类型定义"""
    score: float
    coverage_score: float
    executability_score: float
    clarity_score: float
    suggestions: List[str]
    is_passed: bool


class AgentState(TypedDict):
    """Agent 状态类型定义（LangGraph State Schema）"""
    messages: Annotated[List, add_messages]
    test_cases: List[Dict[str, Any]]
    review_result: Optional[ReviewResult]
    iteration_count: int
    max_iterations: int


# ==================== 状态管理器 ====================

class StateManager:
    """状态管理器：用于在工具函数和 Graph State 之间同步状态
    
    由于工具函数在 Agent 内部调用，无法直接访问 Graph State，
    我们使用这个管理器来桥接状态访问。
    """
    def __init__(self):
        self._state: Dict[str, Any] = {}
    
    def sync_from_graph_state(self, graph_state: Dict[str, Any]) -> None:
        """从 Graph State 同步状态到管理器"""
        self._state = {
            "test_cases": graph_state.get("test_cases", []),
            "review_result": graph_state.get("review_result"),
            "iteration_count": graph_state.get("iteration_count", 0),
            "max_iterations": graph_state.get("max_iterations", 3),
        }
        log.debug(f"状态已从 Graph State 同步: {list(self._state.keys())}")
    
    def sync_to_graph_state(self, graph_state: Dict[str, Any]) -> Dict[str, Any]:
        """将管理器状态同步回 Graph State"""
        graph_state.update(self._state)
        return graph_state
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        return self._state.copy()
    
    def update_state(self, updates: Dict[str, Any]) -> None:
        """更新状态"""
        self._state.update(updates)
        log.debug(f"状态已更新: {list(updates.keys())}")


# 全局状态管理器实例（线程安全通过 LangGraph 的线程隔离保证）
_state_manager = StateManager()


def get_state_manager() -> StateManager:
    """获取状态管理器实例"""
    return _state_manager


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
        state_manager = get_state_manager()
        state = state_manager.get_state()
        
        # 规范化数据格式
        if isinstance(data, dict):
            test_cases = [data]
        elif isinstance(data, list):
            test_cases = data
        else:
            test_cases = [data]
        
        # 更新状态
        state_manager.update_state({
            "test_cases": test_cases,
            "iteration_count": state.get("iteration_count", 0) + 1
        })
        
        count = len(test_cases)
        log.info(f"保存测试用例编写结果: {count} 个测试用例")
        return f"测试用例编写结果已保存: {count} 个测试用例"
    except json.JSONDecodeError as e:
        log.error(f"JSON 解析失败: {e}")
        return f"保存失败: JSON 格式无效 - {str(e)}"
    except Exception as e:
        log.error(f"保存测试用例失败: {e}", exc_info=True)
        return f"保存失败: {str(e)}"


@tool
def get_test_cases() -> str:
    """获取已保存的测试用例编写结果
    
    Returns:
        JSON格式的测试用例列表
    """
    try:
        state_manager = get_state_manager()
        state = state_manager.get_state()
        test_cases = state.get("test_cases", [])
        
        if not test_cases:
            log.warning("获取测试用例: 列表为空")
        
        return json.dumps(test_cases, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"获取测试用例失败: {e}", exc_info=True)
        return json.dumps([], ensure_ascii=False)


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
        state_manager = get_state_manager()
        
        # 验证必需字段
        required_fields = ["score", "coverage_score", "executability_score", 
                          "clarity_score", "is_passed"]
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return f"保存失败: 评审结果缺少必需字段: {missing_fields}"
        
        # 更新状态
        state_manager.update_state({"review_result": data})
        
        score = data.get("score", 0)
        is_passed = data.get("is_passed", False)
        log.info(f"保存评审结果: 得分 {score}/100, 通过: {is_passed}")
        return f"评审结果已保存: 得分 {score}/100, {'通过' if is_passed else '未通过'}"
    except json.JSONDecodeError as e:
        log.error(f"JSON 解析失败: {e}")
        return f"保存失败: JSON 格式无效 - {str(e)}"
    except Exception as e:
        log.error(f"保存评审结果失败: {e}", exc_info=True)
        return f"保存失败: {str(e)}"


@tool
def get_review_result() -> str:
    """获取已保存的评审结果
    
    Returns:
        JSON格式的评审结果
    """
    try:
        state_manager = get_state_manager()
        state = state_manager.get_state()
        review_result = state.get("review_result")
        
        if not review_result:
            log.warning("获取评审结果: 结果为空")
            return json.dumps({}, ensure_ascii=False)
        
        return json.dumps(review_result, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"获取评审结果失败: {e}", exc_info=True)
        return json.dumps({}, ensure_ascii=False)


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
    return create_agent(
        model=llm,
        tools=[save_test_cases, parse_word_document],
        system_prompt=system_prompt,
        name="test_case_generation_agent",
    )


def create_test_case_review_agent_graph():
    """创建测试用例评审专家 Agent（LangGraph 格式）
    
    职责：专注于评审测试用例质量，不负责生成 Excel。
    """
    system_prompt = """你是一个专业的测试用例评审专家。你的任务是：
1. 使用 get_test_cases 工具获取测试用例
2. 对测试用例进行全面评审，从以下维度打分（0-100分）：
   - coverage_score: 覆盖率（是否充分覆盖需求的各种场景）
   - executability_score: 可执行性（步骤是否清晰、可执行）
   - clarity_score: 无歧义性（预期结果是否明确）
3. 总分 = (coverage_score + executability_score + clarity_score) / 3
4. 输出JSON格式的评审结果，并使用 save_review_result 工具保存：
   {{
     "score": 总分,
     "coverage_score": 覆盖率评分,
     "executability_score": 可执行性评分,
     "clarity_score": 无歧义性评分,
     "suggestions": ["优化建议1", "优化建议2"],
     "is_passed": true/false (score >= 90)
   }}
5. 如果评审不通过（score < 90），提供具体的优化建议

评审要严格、客观，确保测试用例质量。你只需要评审，不需要生成Excel文件。"""
    
    # 使用 create_react_agent 创建 LangGraph agent，并指定名称
    return create_agent(
        model=llm,
        tools=[get_test_cases, save_review_result],
        system_prompt=system_prompt,
        name="test_case_review_agent",
    )


# 注意：Excel 生成功能已集成到 Supervisor 中，Supervisor 可以直接调用工具
# 不再需要单独的 excel_generation_agent


# ==================== 创建 Supervisor 系统 ====================

def create_supervisor_system():
    """创建 Supervisor 协调的多 Agent 系统
    
    使用 LangGraph State 系统管理状态，通过 StateManager 在工具函数和 Graph State 之间同步。
    
    优化：直接使用 create_supervisor 返回的 workflow，避免双层 Graph 结构导致的冗余。
    通过包装 invoke/stream 方法来同步状态。
    """
    from langgraph.graph import StateGraph, END
    
    # 创建各个专家 Agent
    test_case_generation_agent = create_test_case_generation_agent_graph()
    test_case_review_agent = create_test_case_review_agent_graph()
    
    # 创建 Supervisor（内部使用 messages 状态）
    # Supervisor 可以直接调用工具，包括 Excel 生成工具
    # 注意：create_supervisor 会为每个 agent 创建 transfer_to_{agent_name} 工具
    # 例如：transfer_to_test_case_generation_agent, transfer_to_test_case_review_agent
    supervisor_graph = create_supervisor(
        agents=[test_case_generation_agent, test_case_review_agent],
        model=llm,
        tools=[get_test_cases, get_review_result, generate_excel_from_test_cases],  # Supervisor 可以直接调用这些工具
        prompt="""你是一个测试用例生成系统的 Supervisor（协调者）。你的任务是协调两个专家 Agent，并在需要时直接调用工具：

可用的 Agent：
1. test_case_generation_agent（测试用例生成专家）：负责根据需求文档生成测试用例。如果用户提供了Word文档路径，该Agent会自动解析Word文档。
2. test_case_review_agent（测试用例评审专家）：负责评审测试用例的质量

可用的工具（你可以直接调用）：
- get_test_cases: 获取已保存的测试用例（返回JSON字符串）
- get_review_result: 获取已保存的评审结果（返回JSON字符串）
- generate_excel_from_test_cases: 生成Excel文件
  参数1：test_cases_json（从get_test_cases获取的JSON字符串）
  参数2：output_path（可选，不传会自动生成）
  参数3：review_result_json（从get_review_result获取的JSON字符串，可选）

工作流程：
1. 当用户提供需求文档（文本或Word文档路径）时，首先调用 test_case_generation_agent 生成测试用例
2. 然后调用 test_case_review_agent 评审测试用例
3. 根据评审结果决定下一步：
   - 如果评审通过（分数>=90），直接调用 generate_excel_from_test_cases 工具生成Excel文件：
     * 先调用 get_test_cases 获取测试用例（JSON字符串）
     * 再调用 get_review_result 获取评审结果（JSON字符串）
     * 最后调用 generate_excel_from_test_cases 生成Excel文件，然后任务完成
   - 如果评审不通过（分数<90），将评审建议反馈给 test_case_generation_agent 进行优化，最多迭代3次
4. 如果迭代3次后仍不通过，也要直接调用 generate_excel_from_test_cases 工具生成Excel文件（包含当前结果），然后任务完成

重要：
- test_case_review_agent 只负责评审，不生成Excel
- Excel 生成由你（Supervisor）直接调用工具完成，不需要通过其他 agent
- 调用 generate_excel_from_test_cases 时，需要传递JSON字符串，不要传递对象

请根据当前状态和任务进度，智能地决定调用哪个 Agent、调用哪个工具，或完成任务。""",
        supervisor_name="supervisor",
    )
    
    # 编译 Supervisor graph
    supervisor_workflow = supervisor_graph.compile()
    
    # 创建状态同步节点函数
    # 使用闭包保存 supervisor_workflow 的引用和 thread_id
    _supervisor_thread_id = "supervisor_main_thread"  # 固定的 thread_id，保持状态连续性
    
    def supervisor_node_with_state_sync(state: AgentState) -> AgentState:
        """Supervisor 节点包装器：在调用前后同步状态
        
        这个函数确保：
        1. 在调用 Supervisor 之前，将 Graph State 同步到 StateManager（供工具函数使用）
        2. 调用 Supervisor workflow（使用 stream 模式和固定的 thread_id 保持状态连续性）
        3. 在调用之后，将 StateManager 的状态同步回 Graph State
        
        关键修复：
        - 使用 stream 模式而不是 invoke，保持状态连续性
        - 使用固定的 thread_id，确保 supervisor_workflow 保持内部状态（包括工具列表）
        - 这样每次调用时，supervisor_workflow 都能访问到完整的工具列表
        """
        state_manager = get_state_manager()
        
        # 1. 从 Graph State 同步到 StateManager（供工具函数使用）
        state_manager.sync_from_graph_state(state)
        
        # 2. 调用原始的 Supervisor workflow（它使用 messages 状态）
        supervisor_state = {"messages": state.get("messages", [])}
        
        # 关键：使用固定的 thread_id 保持状态连续性
        # 这样 supervisor_workflow 可以保持内部状态，包括为每个 agent 添加的 transfer_to_xxx 工具
        config = {"configurable": {"thread_id": _supervisor_thread_id}}
        
        try:
            # 使用 stream 模式保持状态连续性
            # stream 模式可以保持 supervisor_workflow 的内部状态，包括工具列表
            # 这确保了每次调用时，agent 都能访问到完整的工具列表（包括 transfer_to_xxx 工具）
            last_chunk = None
            for chunk in supervisor_workflow.stream(supervisor_state, config=config):
                # 收集最后一个 chunk 作为结果
                last_chunk = chunk
            
            # 从最后一个 chunk 提取 messages
            if last_chunk:
                for node_name, node_output in last_chunk.items():
                    if isinstance(node_output, dict) and "messages" in node_output:
                        state["messages"] = node_output["messages"]
                        break
            else:
                # 如果没有 stream 输出，fallback 到 invoke
                result = supervisor_workflow.invoke(supervisor_state, config=config)
                state["messages"] = result.get("messages", state.get("messages", []))
                
        except Exception as e:
            log.error(f"Supervisor 执行失败: {e}", exc_info=True)
            import traceback
            log.error(traceback.format_exc())
        
        # 3. 从 StateManager 同步回 Graph State
        updated_state = state_manager.sync_to_graph_state(state)
        return updated_state
    
    # 创建自定义 StateGraph，使用我们的 AgentState
    # 这样 LangGraph 服务器可以正确识别它
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("supervisor", supervisor_node_with_state_sync)
    
    # 设置入口点
    workflow.set_entry_point("supervisor")
    
    # 添加结束边
    workflow.add_edge("supervisor", END)
    
    # 编译 workflow（返回真正的 Graph 对象）
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

def initialize_state(max_iterations: int = 3) -> AgentState:
    """初始化 Agent 状态
    
    Args:
        max_iterations: 最大迭代次数，默认 3
    
    Returns:
        初始化后的 AgentState
    """
    initial_state: AgentState = {
        "messages": [],
        "test_cases": [],
        "review_result": None,
        "iteration_count": 0,
        "max_iterations": max_iterations,
    }
    
    # 同步到 StateManager
    state_manager = get_state_manager()
    state_manager.sync_from_graph_state(initial_state)
    
    log.info(f"状态已初始化: max_iterations={max_iterations}")
    return initial_state


