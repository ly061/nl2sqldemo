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
from source.agent.prompts import (
    TEST_CASE_GENERATION_AGENT_PROMPT,
    TEST_CASE_REVIEW_AGENT_PROMPT,
    SUPERVISOR_PROMPT,
)

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
    # 使用 create_agent 创建 LangChain agent，并指定名称
    return create_agent(
        model=llm,
        tools=[save_test_cases, parse_word_document],
        system_prompt=TEST_CASE_GENERATION_AGENT_PROMPT,
        name="test_case_generation_agent",
    )


def create_test_case_review_agent_graph():
    """创建测试用例评审专家 Agent（LangGraph 格式）
    
    职责：专注于评审测试用例质量，不负责生成 Excel。
    """
    # 使用 create_agent 创建 LangChain agent，并指定名称
    return create_agent(
        model=llm,
        tools=[get_test_cases, save_review_result],
        system_prompt=TEST_CASE_REVIEW_AGENT_PROMPT,
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
        prompt=SUPERVISOR_PROMPT,
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


