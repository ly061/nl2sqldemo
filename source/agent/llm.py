import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# 获取环境配置，默认为 prod
# 可在 .env 中设置 APP_ENV=dev 来切换到本地模型
APP_ENV = os.getenv("APP_ENV", "prod").lower()

if APP_ENV == "dev":
    # --- Dev 环境：使用本地大模型 ---
    # 根据用户提供的 curl 信息配置
    LOCAL_API_KEY = "1LtJU5J8KxkjryJtuRfdf1BIriTDV2DE"
    LOCAL_BASE_URL = "http://localhost:8000/api/v1"
    
    # 创建基础 LLM 配置
    # 注意：本地模型可能不支持标准流式格式，强制禁用流式以确保兼容性
    # LangGraph 的流式处理仍然可以工作，只是 LLM 层面不使用流式
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        api_key=LOCAL_API_KEY,
        base_url=LOCAL_BASE_URL,
        # 针对本地接口要求的自定义请求头
        default_headers={
            "X-API-Key": LOCAL_API_KEY
        },
        # 增加超时时间，本地模型可能响应较慢
        timeout=120.0,
        max_retries=2,
        # 关键：禁用流式，因为本地模型的流式响应格式不符合标准
        # 这不会影响 LangGraph 的整体流式处理，只是 LLM 调用使用非流式
        streaming=False
    )
else:
    # --- Prod 环境：使用 DeepSeek 官方接口 ---
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL
    )
