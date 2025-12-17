from typing import List
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import re

class MySQLDatabaseManager:
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string, pool_size=5,pool_recycle=3600)
        self.session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.session()

    def close(self):
        self.session.close()

    def get_table_names(self) -> list[str]:
        inspector = inspect(self.engine)
     
        return inspector.get_table_names()

    def get_tables_names_with_comments(self) -> list[dict]:
        """获取所有表名及其注释
        
        Returns:
            list[dict]: 包含 'name' 和 'comment' 键的字典列表
        """
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()
        result = []
        for table_name in table_names:
            try:
                comment_info = inspector.get_table_comment(table_name)
                result.append({
                    'name': table_name,
                    'comment': comment_info.get('text', '') if comment_info else ''
                })
            except Exception:
                # 如果获取注释失败，仍然返回表名，注释为空
                result.append({
                    'name': table_name,
                    'comment': ''
                })
        return result

    def get_table_columns(self, table_name: str) -> list[dict]:
        """获取表的列信息
        
        Args:
            table_name: 表名
            
        Returns:
            list[dict]: 列信息字典列表，包含 'name', 'type', 'nullable' 等
        """
        inspector = inspect(self.engine)
        return inspector.get_columns(table_name)

    def get_table_data(self, table_name: str, limit: int = 100) -> list[dict]:
        """获取表的数据
        
        Args:
            table_name: 表名
            limit: 限制返回的行数，默认100
            
        Returns:
            list[dict]: 数据行字典列表
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                f"SELECT * FROM {table_name} LIMIT {limit}"
            )
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def get_table_schema(self, table_names: List[str]) -> str:
        """获取表的架构
        
        Args:
            table_names: 表名列表
            
        Returns:
            str: 表架构字符串
        """
        
        result = ""
        for table_name in table_names:
            result += f"表名: {table_name}\n"
            result += f"表架构: {self.get_table_columns(table_name)}\n"
        return result

    def validate_sql(self, sql: str) -> str:
        """验证SQL语句是否正确
        
        Args:
            sql: 要验证的SQL语句
            
        Returns:
            str: 验证结果反馈信息
        """
        if not sql or not sql.strip():
            return "错误: SQL语句为空"
        
        sql = sql.strip()
        
        # 检查是否是SELECT语句（只允许查询操作）
        sql_upper = sql.upper().strip()
        if not sql_upper.startswith('SELECT'):
            return f"错误: 只允许执行SELECT查询语句，当前SQL语句以 '{sql[:20]}...' 开头"
        
        # 检查是否包含危险的SQL操作
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return f"错误: SQL语句包含危险操作 '{keyword}'，只允许执行SELECT查询语句"
        
        # 使用EXPLAIN验证SQL语法
        try:
            with self.engine.connect() as conn:
                # 使用EXPLAIN来验证SQL语法，不会实际执行查询
                explain_sql = f"EXPLAIN {sql}"
                result = conn.execute(text(explain_sql))
                # 尝试获取一行来确认SQL有效
                result.fetchone()
            
            return "验证成功: SQL语句语法正确，是一个有效的SELECT查询语句"
        except Exception as e:
            error_msg = str(e)
            # 提取更友好的错误信息
            if "doesn't exist" in error_msg or "Unknown column" in error_msg:
                return f"验证失败: SQL语句中的表名或列名不存在。错误详情: {error_msg}"
            elif "syntax error" in error_msg.lower() or "SQL syntax" in error_msg:
                return f"验证失败: SQL语法错误。错误详情: {error_msg}"
            else:
                return f"验证失败: {error_msg}"

    def execute_query(self, sql: str) -> str:
        """执行SQL语句,提供执行反馈，输入应为要执行的SQL语句
        
        Args:
            sql: 要执行的SQL语句（只允许SELECT查询）
            
        Returns:
            str: 执行结果反馈信息
        """
        if not sql or not sql.strip():
            return "错误: SQL语句为空"
        
        sql = sql.strip()
        sql_upper = sql.upper().strip()
        
        # 安全检查：只允许SELECT语句
        if not sql_upper.startswith('SELECT'):
            return f"错误: 只允许执行SELECT查询语句，当前SQL语句以 '{sql[:20]}...' 开头"
        
        # 检查是否包含危险的SQL操作
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return f"错误: SQL语句包含危险操作 '{keyword}'，只允许执行SELECT查询语句"
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                rows = result.fetchall()
                columns = result.keys()
                
                if len(rows) == 0:
                    return "SQL语句执行成功，但查询结果为空"
                
                # 格式化结果 - 返回所有数据（最多1000行），避免 agent 陷入循环
                # 如果数据量较小（<=100行），返回所有数据；如果较大，返回前1000行并提示
                max_display_rows = 1000
                display_rows = rows[:max_display_rows] if len(rows) > max_display_rows else rows
                
                result_str = f"SQL语句执行成功，共返回 {len(rows)} 行数据\n"
                result_str += f"列名: {', '.join(columns)}\n"
                
                if len(rows) <= max_display_rows:
                    result_str += f"所有数据（共{len(rows)}行）:\n"
                    for i, row in enumerate(display_rows, 1):
                        result_str += f"  第{i}行: {dict(zip(columns, row))}\n"
                else:
                    result_str += f"前{max_display_rows}行数据（共{len(rows)}行，已显示前{max_display_rows}行）:\n"
                    for i, row in enumerate(display_rows, 1):
                        result_str += f"  第{i}行: {dict(zip(columns, row))}\n"
                    result_str += f"\n注意：查询结果共{len(rows)}行，已显示前{max_display_rows}行。如需查看所有数据，请使用LIMIT和OFFSET进行分页查询。"
                
                return result_str
        except Exception as e:
            return f"SQL语句执行失败，错误信息: {str(e)}"



if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("请设置环境变量 DATABASE_URL，例如: mysql+pymysql://user:password@host:port/database")
    db_manager = MySQLDatabaseManager(DATABASE_URL)
    print(db_manager.get_tables_names_with_comments())
