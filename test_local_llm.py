#!/usr/bin/env python3
"""
测试本地大模型的输出格式
用于诊断前端显示问题

使用方法：
1. 确保本地大模型服务运行在 http://localhost:8000
2. 运行: python3 test_local_llm.py
3. 查看输出，检查响应格式
"""
import os
import sys
import json
import logging
from pathlib import Path

# 设置日志级别为 DEBUG 以便看到详细信息
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 设置环境变量为 dev
os.environ["APP_ENV"] = "dev"

# 添加项目路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 80)
print("测试本地大模型输出格式")
print("=" * 80)
print("\n提示: 如果本地服务未运行，部分测试会失败，但可以看到错误信息")
print("=" * 80)

# 1. 测试直接调用本地API
print("\n[1] 测试直接调用本地API (原始响应)")
print("-" * 80)
try:
    import requests
    
    url = "http://localhost:8000/api/v1/chat/completions"
    headers = {
        "X-API-Key": "1LtJU5J8KxkjryJtuRfdf1BIriTDV2DE",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "你好，请简单介绍一下你自己"}
        ],
        "stream": False,
        "temperature": 0.7
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        raw_response = response.json()
        print(f"原始响应类型: {type(raw_response)}")
        print(f"原始响应键: {raw_response.keys() if isinstance(raw_response, dict) else 'N/A'}")
        
        if "choices" in raw_response:
            choice = raw_response["choices"][0]
            print(f"Choice 键: {choice.keys() if isinstance(choice, dict) else 'N/A'}")
            message = choice.get("message", {})
            print(f"Message 键: {message.keys() if isinstance(message, dict) else 'N/A'}")
            print(f"Message content: {repr(message.get('content'))}")
            print(f"Message content 类型: {type(message.get('content'))}")
            print(f"Message role: {message.get('role')}")
            
            # 打印完整响应（格式化）
            print("\n完整响应 JSON:")
            print(json.dumps(raw_response, indent=2, ensure_ascii=False))
    else:
        print(f"错误: {response.text}")
except Exception as e:
    print(f"直接API调用失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 测试通过LangChain ChatOpenAI调用
print("\n[2] 测试通过 LangChain ChatOpenAI 调用")
print("-" * 80)
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        api_key="1LtJU5J8KxkjryJtuRfdf1BIriTDV2DE",
        base_url="http://localhost:8000/api/v1",
        default_headers={
            "X-API-Key": "1LtJU5J8KxkjryJtuRfdf1BIriTDV2DE"
        }
    )
    
    messages = [HumanMessage(content="你好，请简单介绍一下你自己")]
    response = llm.invoke(messages)
    
    print(f"响应类型: {type(response)}")
    print(f"响应类名: {response.__class__.__name__}")
    print(f"Content: {repr(response.content)}")
    print(f"Content 类型: {type(response.content)}")
    print(f"Content 是否为 None: {response.content is None}")
    print(f"Content 是否为空字符串: {response.content == ''}")
    
    # 检查其他属性
    print(f"\n响应对象属性:")
    for attr in dir(response):
        if not attr.startswith('_'):
            try:
                value = getattr(response, attr)
                if not callable(value):
                    print(f"  {attr}: {repr(value)}")
            except:
                pass
    
    # 检查 tool_calls
    if hasattr(response, 'tool_calls'):
        print(f"\nTool calls: {response.tool_calls}")
    
    # 检查 response_metadata
    if hasattr(response, 'response_metadata'):
        print(f"\nResponse metadata: {response.response_metadata}")
        
except Exception as e:
    print(f"LangChain 调用失败: {e}")
    import traceback
    traceback.print_exc()

# 3. 测试流式输出
print("\n[3] 测试流式输出")
print("-" * 80)
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        api_key="1LtJU5J8KxkjryJtuRfdf1BIriTDV2DE",
        base_url="http://localhost:8000/api/v1",
        default_headers={
            "X-API-Key": "1LtJU5J8KxkjryJtuRfdf1BIriTDV2DE"
        },
        streaming=True
    )
    
    messages = [HumanMessage(content="你好，请简单介绍一下你自己")]
    chunks = []
    for chunk in llm.stream(messages):
        chunks.append(chunk)
        print(f"Chunk 类型: {type(chunk)}")
        print(f"Chunk content: {repr(chunk.content)}")
        print(f"Chunk content 类型: {type(chunk.content)}")
        if len(chunks) >= 3:  # 只打印前3个chunk
            print("... (更多chunks)")
            break
    
    print(f"\n总共收到 {len(chunks)} 个chunks")
    
except Exception as e:
    print(f"流式输出测试失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 测试通过项目中的 llm 模块
print("\n[4] 测试通过项目中的 llm 模块")
print("-" * 80)
try:
    from source.agent.llm import llm
    from langchain_core.messages import HumanMessage
    
    messages = [HumanMessage(content="你好，请简单介绍一下你自己")]
    response = llm.invoke(messages)
    
    print(f"响应类型: {type(response)}")
    print(f"Content: {repr(response.content)}")
    print(f"Content 类型: {type(response.content)}")
    print(f"Content 是否为 None: {response.content is None}")
    
except Exception as e:
    print(f"项目 llm 模块调用失败: {e}")
    import traceback
    traceback.print_exc()

# 5. 测试消息转换函数
print("\n[5] 测试消息转换函数")
print("-" * 80)
try:
    from source.agent.llm import llm
    from langchain_core.messages import HumanMessage, AIMessage
    from api.utils.message_utils import langchain_to_chat_message, convert_message_content_to_string
    
    # 测试实际响应
    messages = [HumanMessage(content="你好")]
    response = llm.invoke(messages)
    
    print(f"原始 AIMessage content: {repr(response.content)}")
    print(f"原始 AIMessage content 类型: {type(response.content)}")
    
    # 测试转换函数
    converted_content = convert_message_content_to_string(response.content)
    print(f"转换后 content: {repr(converted_content)}")
    print(f"转换后 content 类型: {type(converted_content)}")
    
    # 测试完整消息转换
    chat_message = langchain_to_chat_message(response)
    print(f"\nChatMessage 类型: {chat_message.type}")
    print(f"ChatMessage content: {repr(chat_message.content)}")
    print(f"ChatMessage content 类型: {type(chat_message.content)}")
    print(f"ChatMessage model_dump: {chat_message.model_dump()}")
    
except Exception as e:
    print(f"消息转换测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)

