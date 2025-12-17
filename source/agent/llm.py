import os

from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# llm = ChatOpenAI(
#     # model="deepseek-chat",
#     model="deepseek-reasoner",
#     temperature=0.7,
#     api_key=DEEPSEEK_API_KEY,
#     base_url="https://api.deepseek.com")


llm = ChatDeepSeek(
    model="deepseek-chat",  # Using deepseek-chat instead of deepseek-reasoner to avoid reasoning_content issue
    # model="deepseek-reasoner",  # deepseek-reasoner requires reasoning_content field in tool calls, which langchain-deepseek 1.0.1 doesn't fully support
    temperature=0.7,
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com")
