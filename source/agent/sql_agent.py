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

from source.agent.llm import llm
from source.agent.tools.tool_sql_table_list import ToolSqlTableList, ToolSqlTableSchema, SQLQueryTool, SQLQueryCheckerTool
from source.agent.utils.db_utils import MySQLDatabaseManager

# 加载环境变量
load_dotenv()

# 从环境变量读取数据库连接字符串
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:12345678@localhost:3306/sonic")
db_manager = MySQLDatabaseManager(DATABASE_URL)
tool_sql_table_list = ToolSqlTableList(db_manager=db_manager)
tool_sql_table_schema = ToolSqlTableSchema(db_manager=db_manager)
tool_sql_query = SQLQueryTool(db_manager=db_manager)
tool_sql_query_checker = SQLQueryCheckerTool(db_manager=db_manager)




agent = create_agent(
        model=llm,
        tools=[tool_sql_table_list,tool_sql_table_schema,tool_sql_query,tool_sql_query_checker],
        system_prompt="你是一个Mysql智能助手，请使用提供的工具函数进行数据库操作，完成用户的需求"
    )


if __name__ == "__main__":
    for step in agent.stream(input={
        "messages": [
            {
                "role": "user",
                "content": "查询出sonic正在使用哪些设备"
            }
        ]
    }):
        # step 的结构是: {'model': {'messages': [...]}} 或 {'tools': {'messages': [...]}}
        if isinstance(step, dict):
            # 检查是否有 'model' 键（模型响应）
            if "model" in step and "messages" in step["model"]:
                messages = step["model"]["messages"]
                if len(messages) > 0:
                    last_message = messages[-1]
                    if hasattr(last_message, 'content') and last_message.content:
                        print(last_message.content)
            # 检查是否有 'tools' 键（工具调用结果，通常不需要打印）
            # elif "tools" in step and "messages" in step["tools"]:
            #     # 工具消息通常不需要打印，但可以用于调试
            #     pass
            