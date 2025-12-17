
import sys
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到 Python 路径，支持直接运行脚本
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from source.agent.utils.db_utils import MySQLDatabaseManager
from pydantic import BaseModel, Field, create_model
from langchain_core.tools import BaseTool
from source.agent.utils.log_utils import MyLogger

log = MyLogger()



class ToolSqlTableList(BaseTool):
    name: str = "sql_table_list"
    description: str = "获取数据库中的所有表名"
    db_manager: Optional[MySQLDatabaseManager] = Field(default=None, exclude=True)

    def __init__(self, db_manager: MySQLDatabaseManager, **kwargs):
        """初始化工具
        
        Args:
            db_manager: MySQL数据库管理器实例
        """
        super().__init__(**kwargs)
        self.db_manager = db_manager

    def _run(self, query: str = "") -> dict | str:
        """获取数据库中的所有表名及其注释
        
        Args:
            query: 查询参数（此工具不需要参数，但为了兼容性保留）
            
        Returns:
            str: 表名和注释的格式化字符串
        """
        if self.db_manager is None:
            return "错误: 数据库管理器未初始化"
        
        tables_names_with_comments = self.db_manager.get_tables_names_with_comments()

        result = f"总共有{len(tables_names_with_comments)}张表\n"
        n = 1
        for table in tables_names_with_comments:
            comment = table.get('comment') or '无注释'
            result += f"第{n}张表: 表名: {table['name']}, 注释: {comment}\n"
            n += 1

        return result

    async def _arun(self, query: str = "") -> dict | str:
        """异步获取数据库中的所有表名"""
        return self._run(query)

class ToolSqlTableSchema(BaseTool):
    name: str = "sql_table_schema"
    description: str = "获取数据库中的所有表架构"
    db_manager: Optional[MySQLDatabaseManager] = Field(default=None, exclude=True)

    def __init__(self, db_manager: MySQLDatabaseManager, **kwargs):
        """初始化工具
        
        Args:
            db_manager: MySQL数据库管理器实例
        """
        super().__init__(**kwargs)
        self.db_manager = db_manager
        # 定义参数模式
        self.args_schema = create_model(
            "ToolSqlTableSchemaArgs",
            table_names=(Optional[List[str]], Field(default=None, description="表名列表"))
        )

    def _run(self, table_names: Optional[List[str]] = None) -> str:
        """获取表的架构信息
        
        Args:
            table_names: 表名列表
            
        Returns:
            str: 表架构信息字符串
        """
        if self.db_manager is None:
            return "错误: 数据库管理器未初始化"
        if table_names is None or len(table_names) == 0:
            return "错误: 没有传入表名"
        return self.db_manager.get_table_schema(table_names)

    async def _arun(self, table_names: Optional[List[str]] = None) -> str:
        """异步获取表的架构信息"""
        return self._run(table_names)

class SQLQueryTool(BaseTool):
    name: str = "sql_db_query"
    description: str = "执行SELECT SQL查询语句并返回结果"
    db_manager: Optional[MySQLDatabaseManager] = Field(default=None, exclude=True)

    def __init__(self, db_manager: MySQLDatabaseManager, **kwargs):
        """初始化工具
        
        Args:
            db_manager: MySQL数据库管理器实例
        """
        super().__init__(**kwargs)
        self.db_manager = db_manager
        self.args_schema = create_model(
            "SQLQueryToolArgs",
            sql=(str, Field(..., description="要执行的SQL语句"))
        )

    def _run(self, sql: str) -> str:
        """执行SELECT SQL查询语句并返回结果"""
        if self.db_manager is None:
            return "错误: 数据库管理器未初始化"
        if sql is None or len(sql) == 0:
            return "错误: 没有传入SQL语句"
        try:
            result = self.db_manager.execute_query(sql)
            return result
        except Exception as e:
            return f"错误: {e}"

    async def _arun(self, sql: str) -> str:
        """异步执行SELECT SQL查询语句并返回结果"""
        return self._run(sql)

class SQLQueryCheckerTool(BaseTool):
    name: str = "sql_db_query_checker"
    description: str = "检查SQL语句是否是正确,提供验证反馈，输入应为要检查的SQL语句"
    db_manager: Optional[MySQLDatabaseManager] = Field(default=None, exclude=True)

    def __init__(self, db_manager: MySQLDatabaseManager, **kwargs):
        """初始化工具
        
        Args:
            db_manager: MySQL数据库管理器实例
        """
        super().__init__(**kwargs)
        self.db_manager = db_manager
        self.args_schema = create_model(
            "SQLQueryCheckerToolArgs",
            sql=(str, Field(..., description="要检查的SQL语句"))
        )
    
    def _run(self, sql: str) -> str:
        """检查SQL语句是否是正确,提供验证反馈，输入应为要检查的SQL语句"""
        if self.db_manager is None:
            return "错误: 数据库管理器未初始化"
        if sql is None or len(sql) == 0:
            return "错误: 没有传入SQL语句"
        try:
            result = self.db_manager.validate_sql(sql)
            return result
        except Exception as e:
            return f"错误: {e}"
    
    async def _arun(self, sql: str) -> str:
        """异步检查SQL语句是否是正确,提供验证反馈，输入应为要检查的SQL语句"""
        return self._run(sql) 


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:12345678@localhost:3306/sonic")
    db_manager = MySQLDatabaseManager(DATABASE_URL)
    # tool = ToolSqlTableList(db_manager=db_manager)
    # print(tool._run(""))
    # print("======")

    # tool1 = ToolSqlTableSchema(db_manager=db_manager)
    # print(tool1._run(["users"]))

    tool2 = SQLQueryTool(db_manager=db_manager)
    print(tool2._run("SELECT * FROM users"))

    tool3 = SQLQueryCheckerTool(db_manager=db_manager)
    print(tool3._run("SELECT count () * FROM users"))