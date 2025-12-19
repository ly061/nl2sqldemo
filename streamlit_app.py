"""
Streamlit 前端应用
用于测试用例生成系统的交互界面
"""
import sys
import os
from pathlib import Path
import tempfile
import base64
import re

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from source.agent.utils.log_utils import MyLogger
import os
import httpx
import json
import uuid
from typing import Optional, List, Dict, Any

log = MyLogger().get_logger()

# LangGraph服务配置（参考 agent-chat-ui 的配置方式）
LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL", "http://localhost:2024")
LANGGRAPH_API_KEY = os.getenv("LANGSMITH_API_KEY", None)
GRAPH_ID = "agent"  # 使用 graph_id 而不是 assistant_id
ASSISTANT_ID = None  # 将在运行时从创建的 assistant 获取

# 检查服务是否可用（参考 agent-chat-ui 的 checkGraphStatus）
def check_langgraph_service() -> bool:
    """检查LangGraph服务是否可用"""
    try:
        # 参考 agent-chat-ui: 检查 /info 端点
        headers = {}
        if LANGGRAPH_API_KEY:
            headers["X-Api-Key"] = LANGGRAPH_API_KEY
        
        response = httpx.get(
            f"{LANGGRAPH_API_URL}/info",
            headers=headers,
            timeout=2.0
        )
        return response.status_code == 200
    except httpx.ConnectError:
        return False
    except Exception as e:
        log.warning(f"检查服务状态失败: {e}")
        return False

langgraph_service_available = check_langgraph_service()

# 页面配置
st.set_page_config(
    page_title="测试用例生成系统",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items=None
)

# 自定义CSS样式
st.markdown("""
<style>
    /* 隐藏Streamlit默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 主容器样式 */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 1200px;
    }
    
    /* 顶部标题区域 */
    .header-container {
        text-align: center;
        padding: 2rem 0 3rem 0;
        margin-bottom: 2rem;
    }
    
    .header-logo {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        background: #0f766e;
        padding: 12px 24px;
        border-radius: 50px;
        margin-bottom: 1rem;
    }
    
    .header-title {
        font-size: 2rem;
        font-weight: 700;
        color: #1f2937;
        margin: 0;
    }
    
    /* 聊天消息样式 */
    .stChatMessage {
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* 下载链接样式 */
    .download-link {
        display: inline-block;
        padding: 10px 20px;
        background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
        color: white;
        text-decoration: none;
        border-radius: 8px;
        margin-top: 12px;
        font-weight: 500;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(15, 118, 110, 0.2);
    }
    
    .download-link:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(15, 118, 110, 0.4);
        background: linear-gradient(135deg, #14b8a6 0%, #0f766e 100%);
    }
    
    /* 输入区域容器 */
    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        padding: 1.5rem;
        border-top: 1px solid #e5e7eb;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
        z-index: 100;
    }
    
    /* 文件上传按钮样式 */
    .upload-btn-wrapper {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        color: #374151;
        cursor: pointer;
        padding: 8px 12px;
        border-radius: 6px;
        transition: background 0.2s;
    }
    
    .upload-btn-wrapper:hover {
        background: #f3f4f6;
    }
    
    /* 清空按钮样式 */
    .clear-btn {
        background: #f3f4f6;
        color: #374151;
        border: 1px solid #e5e7eb;
        padding: 8px 16px;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .clear-btn:hover {
        background: #e5e7eb;
        border-color: #d1d5db;
    }
</style>
""", unsafe_allow_html=True)

# 初始化session state（参考 agent-chat-ui 的状态管理）
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "assistant_id" not in st.session_state:
    st.session_state.assistant_id = None


def save_uploaded_file(uploaded_file, temp_dir):
    """保存上传的文件到临时目录"""
    file_path = os.path.join(temp_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def process_message(user_input: str, uploaded_file_path: Optional[str] = None, message_placeholder=None):
    """
    处理用户消息并通过 LangGraph API 调用服务
    参考 agent-chat-ui 的实现方式，使用改进的流式处理
    """
    try:
        # 如果有上传的文件，先解析Word文档
        if uploaded_file_path:
            from source.agent.tools.tool_word_parser import _parse_word_from_path
            from pathlib import Path
            with st.spinner("正在解析Word文档..."):
                doc_path = Path(uploaded_file_path)
                paragraphs, tables_content = _parse_word_from_path(doc_path)
                
                # 组合内容
                content_parts = []
                if paragraphs:
                    content_parts.append("\n".join(paragraphs))
                if tables_content:
                    content_parts.append("\n\n表格内容：\n" + "\n\n".join(tables_content))
                
                word_content = "\n\n".join(content_parts) if content_parts else "文档为空"
                # 将解析的内容添加到用户输入中
                user_input = f"{user_input}\n\n[Word文档内容]\n{word_content}"
        
        # 准备请求头（参考 agent-chat-ui 的认证方式）
        headers = {
            "Content-Type": "application/json"
        }
        if LANGGRAPH_API_KEY:
            headers["Authorization"] = f"Bearer {LANGGRAPH_API_KEY}"
            headers["X-Api-Key"] = LANGGRAPH_API_KEY  # 某些部署可能使用这个头
        
        # 确保有 assistant_id（参考图片中的 API 调用方式）
        # 首先尝试创建或获取 assistant（使用 graph_id）
        assistant_id = st.session_state.get("assistant_id")
        if not assistant_id:
            try:
                # 创建 assistant（使用 graph_id）
                create_assistant_data = {
                    "assistant_id": "",  # 空字符串，服务器会生成
                    "graph_id": GRAPH_ID,
                    "config": {},
                    "context": {}
                }
                create_response = httpx.post(
                    f"{LANGGRAPH_API_URL}/assistants",
                    headers=headers,
                    json=create_assistant_data,
                    timeout=5.0
                )
                if create_response.status_code in [200, 201]:
                    assistant_data = create_response.json()
                    assistant_id = assistant_data.get("assistant_id")
                    if assistant_id:
                        st.session_state.assistant_id = assistant_id
                        log.info(f"创建 assistant 成功: {assistant_id}")
                    else:
                        log.warning("创建 assistant 响应中未找到 assistant_id")
                else:
                    log.warning(f"创建 assistant 失败: {create_response.status_code}")
                    assistant_id = None
            except Exception as e:
                log.warning(f"创建 assistant 时出错: {e}")
                assistant_id = None
        
        if not assistant_id:
            return "❌ 无法创建或获取 assistant，请检查 LangGraph 服务配置"
        
        # 确保 thread 存在（使用 assistant_id 创建 thread）
        # 重要：正确的 API 路径是 POST /threads，在请求体中包含 assistant_id
        thread_id = st.session_state.get("thread_id")
        if not thread_id:
            try:
                create_thread_response = httpx.post(
                    f"{LANGGRAPH_API_URL}/threads",
                    headers=headers,
                    json={"assistant_id": assistant_id},  # 在请求体中包含 assistant_id
                    timeout=5.0
                )
                if create_thread_response.status_code in [200, 201]:
                    thread_data = create_thread_response.json()
                    if "thread_id" in thread_data:
                        thread_id = thread_data["thread_id"]
                        st.session_state.thread_id = thread_id
                        log.info(f"创建 thread 成功: {thread_id}")
                    else:
                        log.error("创建 thread 响应中未找到 thread_id")
                        return "❌ 无法创建 thread，服务器响应格式错误"
                else:
                    error_text = create_thread_response.text[:200] if hasattr(create_thread_response, 'text') else str(create_thread_response.status_code)
                    log.error(f"创建 thread 失败: {create_thread_response.status_code}, {error_text}")
                    return f"❌ 无法创建 thread (状态码: {create_thread_response.status_code})"
            except Exception as e:
                log.error(f"创建 thread 时出错: {e}")
                return f"❌ 创建 thread 时出错: {str(e)}"
        
        if not thread_id:
            return "❌ 无法获取 thread_id"
        
        # 构建消息格式（参考 agent-chat-ui 的消息格式）
        # 如果 assistant_id 存在，使用它；否则使用 graph_id
        if assistant_id:
            input_data = {
                "assistant_id": assistant_id,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_input
                        }
                    ]
                }
            }
        else:
            # 使用 graph_id（某些 API 版本可能支持）
            input_data = {
                "graph_id": GRAPH_ID,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_input
                        }
                    ]
                }
            }
        
        # 使用流式API端点（参考 agent-chat-ui: streamMode: ["values"]）
        # 对应 LangGraph API: POST /threads/{thread_id}/runs/stream
        url = f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs/stream"
        
        # 实时处理流式响应（参考 agent-chat-ui 的流式处理）
        accumulated_response = ""
        last_message_content = ""
        all_messages = []
        
        try:
            with httpx.stream(
                "POST",
                url,
                json=input_data,
                headers=headers,
                timeout=300.0
            ) as stream_response:
                if stream_response.status_code != 200:
                    error_text = ""
                    try:
                        for chunk in stream_response.iter_bytes():
                            error_text += chunk.decode('utf-8', errors='ignore')
                            if len(error_text) > 1000:
                                break
                    except Exception as e:
                        error_text = f"HTTP {stream_response.status_code}: {str(e)}"
                    return f"❌ API请求失败 (状态码: {stream_response.status_code})\n\n{error_text[:500]}"
                
                # 处理SSE格式的流式响应（参考 agent-chat-ui 的流式处理）
                for line in stream_response.iter_lines():
                    if not line:
                        continue
                    
                    try:
                        # 处理SSE格式: data: {...}
                        if line.startswith("data: "):
                            data_str = line[6:]  # 移除 "data: " 前缀
                            if data_str.strip() == "[DONE]":
                                break
                            
                            if data_str.strip():
                                event_data = json.loads(data_str)
                                
                                # 处理不同类型的事件（参考 agent-chat-ui 的事件处理）
                                event_type = event_data.get("type", "")
                                
                                if event_type == "messages":
                                    # 处理消息事件
                                    messages_data = event_data.get("data", [])
                                    if isinstance(messages_data, list):
                                        all_messages.extend(messages_data)
                                        
                                        # 提取最后一条AI消息并实时更新
                                        for msg in reversed(messages_data):
                                            if isinstance(msg, dict):
                                                role = msg.get("role") or msg.get("type", "")
                                                if role in ["assistant", "ai"]:
                                                    content = msg.get("content", "")
                                                    if isinstance(content, list):
                                                        # 处理multimodal内容
                                                        text_parts = []
                                                        for item in content:
                                                            if isinstance(item, dict):
                                                                if item.get("type") == "text":
                                                                    text_parts.append(item.get("text", ""))
                                                                elif "text" in item:
                                                                    text_parts.append(item["text"])
                                                        content = "\n".join(text_parts) if text_parts else ""
                                                    
                                                    if isinstance(content, str) and content:
                                                        # 流式更新：只显示新增内容
                                                        if content != last_message_content:
                                                            accumulated_response = content
                                                            last_message_content = content
                                                            
                                                            # 实时更新 UI（参考 agent-chat-ui）
                                                            if message_placeholder:
                                                                message_placeholder.markdown(accumulated_response)
                                                        break
                                
                                elif event_type == "state":
                                    # 处理状态更新（参考 agent-chat-ui: streamMode: ["values"]）
                                    state_data = event_data.get("data", {})
                                    if isinstance(state_data, dict) and "messages" in state_data:
                                        messages = state_data["messages"]
                                        if messages:
                                            all_messages = messages
                                            
                                            # 提取最后一条AI消息
                                            for msg in reversed(messages):
                                                if isinstance(msg, dict):
                                                    role = msg.get("role") or msg.get("type", "")
                                                    if role in ["assistant", "ai"]:
                                                        content = msg.get("content", "")
                                                        if isinstance(content, list):
                                                            text_parts = []
                                                            for item in content:
                                                                if isinstance(item, dict):
                                                                    if item.get("type") == "text":
                                                                        text_parts.append(item.get("text", ""))
                                                                    elif "text" in item:
                                                                        text_parts.append(item["text"])
                                                            content = "\n".join(text_parts) if text_parts else ""
                                                        
                                                        if isinstance(content, str) and content:
                                                            accumulated_response = content
                                                            last_message_content = content
                                                            
                                                            # 实时更新 UI
                                                            if message_placeholder:
                                                                message_placeholder.markdown(accumulated_response)
                                                            break
                                
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        log.warning(f"解析响应行失败: {e}")
                        continue
            
            # 如果没有流式更新，尝试获取最终状态（参考 agent-chat-ui 的fallback）
            if not accumulated_response:
                try:
                    # 正确的 API 路径是 GET /threads/{thread_id}
                    thread_url = f"{LANGGRAPH_API_URL}/threads/{thread_id}"
                    thread_response = httpx.get(thread_url, headers=headers, timeout=10.0)
                    if thread_response.status_code == 200:
                            thread_data = thread_response.json()
                            if "values" in thread_data and "messages" in thread_data["values"]:
                                messages = thread_data["values"]["messages"]
                                if messages:
                                    for msg in reversed(messages):
                                        if isinstance(msg, dict):
                                            role = msg.get("role") or msg.get("type", "")
                                            if role in ["assistant", "ai"]:
                                                content = msg.get("content", "")
                                                if isinstance(content, str):
                                                    accumulated_response = content
                                                    break
                except Exception as e:
                    log.warning(f"获取thread状态失败: {e}")
            
            if not accumulated_response:
                accumulated_response = "未收到响应，请检查LangGraph服务是否正常运行"
            
            return accumulated_response
            
        except httpx.ConnectError:
            return f"""❌ 无法连接到LangGraph服务

请确保LangGraph服务正在运行：
```bash
langgraph dev
```

**服务地址**: `{LANGGRAPH_API_URL}`

**检查步骤**:
1. 确认 `langgraph dev` 命令已执行
2. 检查服务是否在 `{LANGGRAPH_API_URL}` 上运行
3. 查看终端是否有错误信息"""
        except Exception as api_error:
            log.error(f"API调用错误: {str(api_error)}")
            import traceback
            error_detail = traceback.format_exc()
            error_msg = str(api_error)
            return f"❌ API调用错误: {error_msg}\n\n<details><summary>错误详情</summary>\n\n```\n{error_detail}\n```\n</details>"
        
    except Exception as e:
        log.error(f"处理消息时出错: {str(e)}")
        import traceback
        error_detail = traceback.format_exc()
        return f"❌ 错误: {str(e)}\n\n<details><summary>错误详情</summary>\n\n```\n{error_detail}\n```\n</details>"


def get_excel_files():
    """获取downloads目录中的所有Excel文件"""
    downloads_dir = Path(__file__).parent / "downloads"
    if downloads_dir.exists():
        return sorted(
            downloads_dir.glob("*.xlsx"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
    return []


def create_download_link(file_path):
    """创建下载链接"""
    with open(file_path, "rb") as f:
        file_data = f.read()
        b64 = base64.b64encode(file_data).decode()
        filename = Path(file_path).name
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}" class="download-link">📥 下载 {filename}</a>'
        return href


def extract_excel_filename(text):
    """从文本中提取Excel文件名"""
    match = re.search(r'测试用例_\d+_\d+\.xlsx', text)
    return match.group() if match else None


# 隐藏侧边栏
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# 顶部标题区域
st.markdown("""
<div class="header-container">
    <div class="header-logo">
        <span style="font-size: 24px;">📋</span>
        <span style="font-size: 20px; color: white; font-weight: 600;">测试用例生成</span>
    </div>
</div>
""", unsafe_allow_html=True)


# 主聊天区域 - 添加底部padding避免被输入框遮挡
st.markdown("""
<style>
    .main .block-container {
        padding-bottom: 200px;
    }
</style>
""", unsafe_allow_html=True)

# 显示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        content = message["content"]
        
        # 检查是否包含Excel文件信息
        excel_filename = extract_excel_filename(content)
        if excel_filename:
            excel_path = Path(__file__).parent / "downloads" / excel_filename
            if excel_path.exists():
                # 替换文本中的下载链接为可点击的链接
                download_link = create_download_link(excel_path)
                # 移除原有的下载链接文本，替换为HTML链接
                content = re.sub(
                    r'\[点击下载Excel文件\]\([^\)]+\)',
                    download_link,
                    content
                )
                content = re.sub(
                    r'/api/download/[^\s\n]+',
                    download_link,
                    content
                )
                # 如果内容中没有链接，在末尾添加
                if download_link not in content:
                    content += f"\n\n{download_link}"
        
        st.markdown(content, unsafe_allow_html=True)

# 底部输入区域 - 固定在底部
st.markdown("---")

# 输入区域布局 - 清空按钮在中间
input_col1, input_col2, input_col3 = st.columns([6, 1, 3])

with input_col1:
    user_input = st.chat_input("Type your message...", key="main_input")

with input_col2:
    # 清空按钮放在中间
    if st.button("清空", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.session_state.thread_id = None
        st.session_state.uploaded_file = None
        st.session_state.assistant_id = None  # 清空 assistant_id，下次会重新创建
        st.rerun()

with input_col3:
    # 文件上传放到可展开组件中
    with st.expander("📎 上传文件", expanded=False):
        uploaded_file = st.file_uploader(
            "选择Word文档",
            type=["docx", "doc"],
            key="file_uploader",
            help="支持 .docx 和 .doc 格式的Word文档"
        )
        if uploaded_file:
            st.session_state.uploaded_file = uploaded_file
            st.success(f"✅ 已上传: {uploaded_file.name}")
        else:
            st.info("请选择要上传的Word文档")

# 处理用户输入
if user_input:
    # 保存用户消息
    user_message = user_input
    if st.session_state.get("uploaded_file"):
        user_message += f"\n\n[已上传文件: {st.session_state.uploaded_file.name}]"
    
    st.session_state.messages.append({"role": "user", "content": user_message})
    
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_input)
        if st.session_state.get("uploaded_file"):
            st.caption(f"📎 {st.session_state.uploaded_file.name}")
    
    # 显示AI响应占位符（用于流式更新）
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤖 AI正在思考...")
    
    # 处理上传的文件
    uploaded_file_path = None
    if st.session_state.get("uploaded_file"):
        # 创建临时目录保存文件
        temp_dir = tempfile.mkdtemp()
        try:
            uploaded_file_path = save_uploaded_file(st.session_state.uploaded_file, temp_dir)
            # 处理消息（传入占位符用于流式更新）
            response = process_message(user_input, uploaded_file_path, message_placeholder)
        finally:
            # 清理临时文件
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        # 清空上传的文件
        st.session_state.uploaded_file = None
    else:
        # 处理纯文本消息（传入占位符用于流式更新）
        response = process_message(user_input, None, message_placeholder)
    
    # 最终更新响应（包含Excel文件链接等）
    if response:
        # 检查响应中是否包含Excel文件信息
        excel_filename = extract_excel_filename(response)
        final_response = response
        if excel_filename:
            excel_path = Path(__file__).parent / "downloads" / excel_filename
            if excel_path.exists():
                # 添加下载链接到响应中
                download_link = create_download_link(excel_path)
                # 替换或添加下载链接
                if "下载链接" in response or "/api/download" in response:
                    final_response = re.sub(
                        r'\[点击下载Excel文件\]\([^\)]+\)',
                        download_link,
                        response
                    )
                    final_response = re.sub(
                        r'/api/download/[^\s\n]+',
                        download_link,
                        final_response
                    )
                else:
                    final_response = response + f"\n\n{download_link}"
        
        # 更新最终响应
        message_placeholder.markdown(final_response, unsafe_allow_html=True)
        
        # 保存AI消息
        st.session_state.messages.append({"role": "assistant", "content": final_response})
    
    # 重新运行以更新界面
    st.rerun()

# 如果没有消息，显示欢迎信息
if not st.session_state.messages:
    # 检查LangGraph服务连接
    service_status = "✅" if langgraph_service_available else "❌"
    service_info = f"LangGraph服务: {LANGGRAPH_API_URL}" if langgraph_service_available else "LangGraph服务未连接"
    
    st.markdown("""
    <div style='text-align: center; padding: 4rem 2rem; color: #6b7280;'>
        <div style='font-size: 3rem; margin-bottom: 1rem;'>✨</div>
        <p style='font-size: 1.2rem; margin-bottom: 0.5rem; font-weight: 600; color: #374151;'>欢迎使用测试用例生成系统</p>
        <p style='font-size: 0.95rem; color: #6b7280; margin-bottom: 1.5rem;'>上传Word文档或输入需求描述，系统将自动生成测试用例</p>
        <div style='padding: 1rem; background: #f3f4f6; border-radius: 8px; display: inline-block; margin-top: 1rem;'>
            <p style='font-size: 0.85rem; color: #6b7280; margin: 0;'>{}</p>
            <p style='font-size: 0.75rem; color: #9ca3af; margin: 0.25rem 0 0 0;'>{}</p>
        </div>
    </div>
    """.format(service_status, service_info), unsafe_allow_html=True)
    
    # 如果服务未连接，显示提示
    if not langgraph_service_available:
        st.warning(f"""
        ⚠️ **LangGraph服务未连接**
        
        请确保LangGraph服务正在运行：
        ```bash
        langgraph dev
        ```
        
        当前配置的服务地址: `{LANGGRAPH_API_URL}`
        
        您可以通过环境变量修改：
        ```bash
        export LANGGRAPH_API_URL=http://localhost:2024
        export LANGSMITH_API_KEY=your_api_key  # 如果需要认证
        ```
        """)


