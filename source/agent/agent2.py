from langchain.agents import create_agent

from source.agent.tools.tool_websearch2 import MyWebSearchTool
from source.agent.llm import llm
from source.agent.tools.tool_websearch1 import web_search


web_search2 = MyWebSearchTool()

agent = create_agent(
        model=llm,
        tools=[web_search2],
        system_prompt="你是一个智能助手，请使用web_search函数搜索网页"
    )


