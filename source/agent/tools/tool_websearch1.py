# 第一种定义工具的方式：使用@tool装饰器


from ast import main
from random import random
import string
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from tavily import TavilyClient
from dotenv import load_dotenv
import os

load_dotenv()  
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


@tool("web_search_tool", parse_docstring=True)
def web_search(query: str) -> dict | str:
    """tavily搜索引擎搜索网页
    
    Args:
        query: 搜索关键词
    
    Returns:
        str: 搜索结果
    """
    try:        
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        results = tavily_client.search(query=query)
        print("搜索成功================================================")
        return results
    except Exception as e:
        print("搜索失败================================================")
        return f"搜索结果: {e}"


class RandomString(BaseModel):
    length: int = Field(...,description="字符串长度")

if __name__ == "__main__":
    print(f"Tool name: {web_search.name}")
    print(f"Tool description: {web_search.description}")
    print(f"Tool args_schema: {web_search.args_schema}")
    print(f"Tool invoke test: {web_search.invoke({'query': '成都明天天气如何'})}")
