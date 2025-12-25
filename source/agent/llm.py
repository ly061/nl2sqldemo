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
        # 注意：保持 streaming 默认值（True），让 LangGraph 决定是否使用流式
        # 如果本地模型流式响应有问题，会在 supervisor 节点中捕获并处理
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
