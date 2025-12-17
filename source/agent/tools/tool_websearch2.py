# 第二种定义工具的方式：使用BaseTool类

from ast import main
from random import random
import string
from langchain_core.tools import tool, BaseTool
from pydantic import BaseModel, Field
from tavily import TavilyClient
from dotenv import load_dotenv
import os

load_dotenv()  
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


class ArgsSchema(BaseModel):
    query: str = Field(..., description="搜索关键词")

class MyWebSearchTool(BaseTool):
    name: str = "web_search_tool2"
    description: str = "tavily搜索引擎搜索网页"
    args_schema: type[BaseModel] = ArgsSchema


    def _run(self, query: str) -> dict | str:
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

