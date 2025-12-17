import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径，支持直接运行脚本
# 必须在所有导入语句之前执行，因为导入语句在模块级别就会执行
# 文件路径: source/agent/sql_agent.py -> 向上3级到项目根目录
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.agents.middleware.human_in_the_loop import InterruptOnConfig


from source.agent.llm import llm
from source.agent.tools.tool_sql_table_list import ToolSqlTableList, ToolSqlTableSchema, SQLQueryTool, SQLQueryCheckerTool
from source.agent.utils.db_utils import MySQLDatabaseManager

# 加载环境变量
load_dotenv()

# 从环境变量读取数据库连接字符串
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("请设置环境变量 DATABASE_URL，例如: mysql+pymysql://user:password@host:port/database")
db_manager = MySQLDatabaseManager(DATABASE_URL)
tool_sql_table_list = ToolSqlTableList(db_manager=db_manager)
tool_sql_table_schema = ToolSqlTableSchema(db_manager=db_manager)
tool_sql_query = SQLQueryTool(db_manager=db_manager)
tool_sql_query_checker = SQLQueryCheckerTool(db_manager=db_manager)

# 配置 HumanInTheLoopMiddleware，指定所有数据库工具都需要用户确认
human_in_the_loop_middleware = HumanInTheLoopMiddleware(
    interrupt_on={
        tool_sql_table_list.name: InterruptOnConfig(
            allowed_decisions=["approve", "reject"]
        ),
        tool_sql_table_schema.name: InterruptOnConfig(
            allowed_decisions=["approve", "reject"]
        ),
        tool_sql_query.name: InterruptOnConfig(
            allowed_decisions=["approve", "reject", "edit"]
        ),
        tool_sql_query_checker.name: InterruptOnConfig(
            allowed_decisions=["approve", "reject"]
        ),
    },
    description_prefix="⚠️  数据库工具执行需要您的批准"
)

agent = create_agent(
        model=llm,
        tools=[tool_sql_table_list, tool_sql_table_schema, tool_sql_query, tool_sql_query_checker],
        middleware=[human_in_the_loop_middleware],
        system_prompt="你是一个Mysql智能助手，请使用提供的工具函数进行数据库操作，完成用户的需求"
    )


def get_user_decision() -> str:
    """获取用户决策"""
    while True:
        user_input = input("\n请选择操作 (approve/reject/edit): ").strip().lower()
        if user_input in ['approve', 'reject', 'edit', 'a', 'r', 'e']:
            if user_input == 'a':
                return 'approve'
            elif user_input == 'r':
                return 'reject'
            elif user_input == 'e':
                return 'edit'
            return user_input
        else:
            print("⚠️  请输入 approve/reject/edit (或 a/r/e)")


if __name__ == "__main__":
    from langgraph.types import Command
    
    # 使用 stream 模式以便处理中断
    config = {"configurable": {"thread_id": "1"}}
    
    # 初始输入
    input_data = {
        "messages": [
            {
                "role": "user",
                "content": "查询users表的结构"
            }
        ]
    }
    
    # 流式处理，检查中断
    interrupted = False
    for step in agent.stream(input_data, config=config, stream_mode="updates"):
        # 检查是否有中断
        if "__interrupt__" in step:
            interrupted = True
            break
        
        # 正常输出步骤信息
        for node_name, node_output in step.items():
            if node_name == "messages" and isinstance(node_output, dict):
                for msg_key, messages in node_output.items():
                    if messages and len(messages) > 0:
                        last_msg = messages[-1]
                        if hasattr(last_msg, 'content') and last_msg.content:
                            print(last_msg.content)
    
    # 如果有中断，处理用户确认
    if interrupted:
        # 获取当前状态
        state = agent.get_state(config)
        interrupt_value = state.values.get("__interrupt__")
        
        print("\n" + "="*60)
        print("⚠️  需要您的批准才能继续执行数据库操作")
        print("="*60)
        
        # 显示工具调用信息
        if interrupt_value and hasattr(interrupt_value, 'action_requests'):
            if interrupt_value.action_requests:
                action = interrupt_value.action_requests[0]
                print(f"工具名称: {action.name}")
                print(f"参数: {action.args}")
                if "sql" in action.args:
                    sql = action.args["sql"]
                    print(f"SQL 语句: {sql[:200]}{'...' if len(sql) > 200 else ''}")
        print("="*60)
        
        # 获取用户决策
        decision = get_user_decision()
        
        # 构建决策命令 - 使用 submit 而不是 stream，传递空输入
        if decision == "approve":
            command = Command(resume={"decisions": [{"type": "approve"}]})
        elif decision == "reject":
            command = Command(resume={"decisions": [{"type": "reject"}]})
        elif decision == "edit":
            # 对于 edit，需要用户提供修改后的参数
            print("\n请输入修改后的 SQL 语句:")
            edited_sql = input("SQL: ").strip()
            if interrupt_value and interrupt_value.action_requests:
                action = interrupt_value.action_requests[0]
                command = Command(resume={
                    "decisions": [{
                        "type": "edit",
                        "edited_action": {
                            "name": action.name,
                            "args": {"sql": edited_sql}
                        }
                    }]
                })
            else:
                command = Command(resume={"decisions": [{"type": "reject"}]})
        else:
            command = Command(resume={"decisions": [{"type": "reject"}]})
        
        # 恢复执行 - 使用 submit 传递空输入，让系统从检查点恢复
        for step_after in agent.stream(
            {},  # 空输入，从检查点恢复
            config=config,
            stream_mode="updates"
        ):
            # 检查是否还有中断
            if "__interrupt__" in step_after:
                print("⚠️  仍有中断，需要继续处理")
                break
            
            # 输出消息
            if "messages" in step_after:
                for node_name, messages in step_after["messages"].items():
                    if messages and len(messages) > 0:
                        last_msg = messages[-1]
                        if hasattr(last_msg, 'content') and last_msg.content:
                            print(last_msg.content)