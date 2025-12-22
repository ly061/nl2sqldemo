"""
Streamlit 前端应用
用于测试用例生成系统的交互界面
使用项目 API (AgentClient)
"""
import sys
import os
import asyncio
from pathlib import Path
import tempfile
import base64
import re
from collections.abc import AsyncGenerator
from typing import Optional, List, Dict, Any

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import uuid
import httpx

from source.agent.utils.log_utils import MyLogger
from agent_client import AgentClient, AgentClientError
from api.schema import ChatMessage

log = MyLogger().get_logger()

# API 服务配置
# 默认使用 9000 端口
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:9000")

APP_TITLE = "测试用例生成系统"
APP_ICON = "📋"


def check_api_service() -> bool:
    """检查 API 服务是否可用"""
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


# 页面配置
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
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
    
    /* 主容器底部padding */
    .main .block-container {
        padding-bottom: 200px;
    }
    
    /* 隐藏侧边栏 */
    section[data-testid="stSidebar"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# 初始化 session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    thread_id = st.query_params.get("thread_id") or str(uuid.uuid4())
    st.session_state.thread_id = thread_id
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "agent_client" not in st.session_state:
    st.session_state.agent_client = AgentClient(base_url=API_BASE_URL)

agent_client: AgentClient = st.session_state.agent_client

# 加载历史消息
if "thread_id" in st.session_state and st.session_state.thread_id:
    try:
        history = agent_client.get_history(thread_id=st.session_state.thread_id)
        if history.messages:
            # 转换为 session_state 格式
            st.session_state.messages = [
                {
                    "role": "user" if msg.type == "human" else "assistant",
                    "content": msg.content
                }
                for msg in history.messages
            ]
    except AgentClientError:
        # 如果获取历史失败，使用空列表
        pass


def save_uploaded_file(uploaded_file, temp_dir: str) -> str:
    """保存上传的文件到临时目录"""
    file_path = os.path.join(temp_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def parse_word_document(file_path: str) -> str:
    """解析 Word 文档"""
    try:
        from source.agent.tools.tool_word_parser import _parse_word_from_path
        from pathlib import Path
        
        doc_path = Path(file_path)
        paragraphs, tables_content = _parse_word_from_path(doc_path)
        
        content_parts = []
        if paragraphs:
            content_parts.append("\n".join(paragraphs))
        if tables_content:
            content_parts.append("\n\n表格内容：\n" + "\n\n".join(tables_content))
        
        return "\n\n".join(content_parts) if content_parts else "文档为空"
    except Exception as e:
        log.error(f"解析Word文档失败: {e}")
        return f"文档解析失败: {str(e)}"


def extract_excel_filename(text: str) -> Optional[str]:
    """从文本中提取Excel文件名"""
    match = re.search(r'测试用例_\d+_\d+\.xlsx', text)
    return match.group() if match else None


def create_download_link(file_path: Path) -> str:
    """创建下载链接"""
    with open(file_path, "rb") as f:
        file_data = f.read()
        b64 = base64.b64encode(file_data).decode()
        filename = file_path.name
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}" class="download-link">📥 下载 {filename}</a>'
        return href


def process_message_content(content: str) -> str:
    """处理消息内容，添加Excel下载链接等"""
    excel_filename = extract_excel_filename(content)
    if excel_filename:
        excel_path = Path(__file__).parent / "downloads" / excel_filename
        if excel_path.exists():
            download_link = create_download_link(excel_path)
            if "下载链接" in content or "/api/download" in content:
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
            else:
                content = content + f"\n\n{download_link}"
    
    return content


async def draw_messages(
    messages_agen: AsyncGenerator[ChatMessage | str, None],
    is_new: bool = False,
) -> None:
    """
    统一绘制所有消息，确保历史和实时流显示完全一致
    参考 AgentHub-main 的实现
    """
    streaming_content = ""
    streaming_placeholder = None
    last_was_ai = False
    
    # 用于匹配 tool_call_id 的 status 容器
    tool_statuses: Dict[str, Any] = {}
    
    try:
        async for msg in messages_agen:
            # 实时 token 流
            if isinstance(msg, str):
                if not streaming_placeholder:
                    chat = st.chat_message("ai")
                    st.session_state.last_message = chat
                    streaming_placeholder = chat.empty()
                streaming_content += msg
                streaming_placeholder.markdown(streaming_content)
                continue
            
            if not isinstance(msg, ChatMessage):
                continue
            
            # 新消息加入历史
            if is_new and msg.content:
                # 检查是否已存在相同的消息
                existing_messages = st.session_state.messages or []
                is_duplicate = False
                for existing in existing_messages:
                    if (existing.get("role") == (msg.type if msg.type != "ai" else "assistant") and
                        existing.get("content") == msg.content):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    st.session_state.messages.append({
                        "role": msg.type if msg.type != "ai" else "assistant",
                        "content": msg.content
                    })
            
            # ==================== 绘制消息 ====================
            if msg.type == "human":
                with st.chat_message("human"):
                    st.markdown(msg.content)
                last_was_ai = False
            
            elif msg.type == "ai":
                # AI 消息可能有 content + tool_calls
                if not last_was_ai:
                    chat = st.chat_message("ai")
                    st.session_state.last_message = chat
                    last_was_ai = True
                else:
                    chat = st.session_state.last_message
                
                with chat:
                    # 显示文本内容
                    if msg.content:
                        processed_content = process_message_content(msg.content)
                        if streaming_placeholder:
                            streaming_placeholder.markdown(processed_content, unsafe_allow_html=True)
                            streaming_placeholder = None
                            streaming_content = ""
                        else:
                            st.markdown(processed_content, unsafe_allow_html=True)
                    
                    # 显示工具调用（如果有）
                    if msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_id = tool_call.get("id", "")
                            tool_name = tool_call.get("name", "unknown")
                            label = f"🛠️ 正在调用工具：**{tool_name}**"
                            status = st.status(label, expanded=True)
                            with status:
                                st.write("**输入参数：**")
                                st.json(tool_call.get("args", {}))
                            tool_statuses[tool_id] = (status, tool_name)
            
            elif msg.type == "tool":
                # 查找对应的工具调用 status 并更新
                status_tuple = tool_statuses.get(msg.tool_call_id or "")
                if status_tuple:
                    status, tool_name = status_tuple
                    with status:
                        st.write("**工具执行结果：**")
                        st.markdown(msg.content)
                    status.update(
                        label=f"✅ 已执行工具 {tool_name}",
                        state="complete",
                    )
                else:
                    with st.chat_message("assistant", avatar="🛠️"):
                        st.caption("工具执行结果")
                        st.markdown(msg.content)
                last_was_ai = True
            
            elif msg.type == "interrupt":
                # 中断消息（HITL - Human in the Loop）
                if is_new:
                    st.session_state.pending_interrupt = msg
                    with st.chat_message("system"):
                        st.warning("🤖 Agent 请求人工审核")
            
            # 清除 streaming 状态
            streaming_placeholder = None
            streaming_content = ""
    
    except Exception as e:
        st.error(f"绘制消息时出错: {e}")
        log.error(f"绘制消息时出错: {e}", exc_info=True)
    finally:
        # 确保所有 status 关闭
        for s in tool_statuses.values():
            try:
                if isinstance(s, tuple):
                    s[0].update(state="complete")
            except Exception:
                pass


async def main() -> None:
    """主应用函数"""
    # 检查服务状态
    api_service_available = check_api_service()
    
    # 顶部标题区域
    st.markdown(f"""
    <div class="header-container">
        <div class="header-logo">
            <span style="font-size: 24px;">{APP_ICON}</span>
            <span style="font-size: 20px; color: white; font-weight: 600;">测试用例生成</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 显示历史消息
    messages: List[Dict] = st.session_state.messages or []
    
    # 直接显示历史消息
    for message in messages:
        role = message.get("role", "assistant")
        content = message.get("content", "")
        
        if not content:
            continue
        
        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
        elif role == "assistant":
            with st.chat_message("ai"):
                processed_content = process_message_content(content)
                st.markdown(processed_content, unsafe_allow_html=True)
    
    # 如果没有消息，显示欢迎信息
    if not messages:
        st.markdown(f"""
        <div style='text-align: center; padding: 4rem 2rem; color: #6b7280;'>
            <div style='font-size: 3rem; margin-bottom: 1rem;'>✨</div>
            <p style='font-size: 1.2rem; margin-bottom: 0.5rem; font-weight: 600; color: #374151;'>欢迎使用测试用例生成系统</p>
            <p style='font-size: 0.95rem; color: #6b7280; margin-bottom: 1.5rem;'>上传Word文档或输入需求描述，系统将自动生成测试用例</p>
        </div>
        """, unsafe_allow_html=True)
        
        if not api_service_available:
            st.warning(f"""
            ⚠️ **API服务未连接**
            
            请确保API服务正在运行：
            ```bash
            uvicorn api.main:app --host 0.0.0.0 --port 9000
            ```
            
            当前配置的服务地址: `{API_BASE_URL}`
            
            您可以通过环境变量修改：
            ```bash
            export API_BASE_URL=http://localhost:9000
            ```
            """)
    
    # 底部输入区域
    st.markdown("---")
    
    # 输入区域布局
    input_col1, input_col2, input_col3 = st.columns([6, 1, 3])
    
    with input_col1:
        user_input = st.chat_input("Type your message...", key="main_input")
    
    with input_col2:
        # 清空按钮
        if st.button("清空", use_container_width=True, type="secondary"):
            for key in ["messages", "thread_id", "uploaded_file"]:
                st.session_state.pop(key, None)
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()
    
    with input_col3:
        # 文件上传
        with st.expander("📎 上传文件", expanded=False):
            uploaded_file = st.file_uploader(
                "选择Word文档",
                type=["docx", "doc"],
                key="file_uploader",
                help="支持 .docx 和 .doc 格式的Word文档"
            )
            if uploaded_file:
                # 只有当文件是新上传的（与之前的不同）时才更新
                if (not st.session_state.get("uploaded_file") or 
                    st.session_state.uploaded_file.name != uploaded_file.name):
                    st.session_state.uploaded_file = uploaded_file
                    st.success(f"✅ 已上传: {uploaded_file.name}")
                else:
                    st.info(f"📎 已选择: {uploaded_file.name}（将在发送消息时处理）")
            else:
                # 如果用户清空了文件选择，也清空 session_state
                if st.session_state.get("uploaded_file"):
                    st.session_state.uploaded_file = None
                st.info("请选择要上传的Word文档")
    
    # 处理用户输入
    if user_input:
        # 处理上传的文件
        uploaded_file_path = None
        final_user_input = user_input
        has_uploaded_file = False
        
        # 只在本次有上传文件时才处理 Word 文档
        if st.session_state.get("uploaded_file"):
            has_uploaded_file = True
            # 创建临时目录保存文件
            temp_dir = tempfile.mkdtemp()
            try:
                uploaded_file_path = save_uploaded_file(st.session_state.uploaded_file, temp_dir)
                with st.spinner("正在解析Word文档..."):
                    word_content = parse_word_document(uploaded_file_path)
                    # 只在发送给 Agent 的消息中包含 Word 文档内容
                    final_user_input = f"{user_input}\n\n[Word文档内容]\n{word_content}"
            finally:
                # 清理临时文件
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
            # 立即清空上传的文件，避免下次对话重复使用
            st.session_state.uploaded_file = None
        
        # 保存用户消息：只保存原始输入，不包含 Word 文档内容
        # 这样历史消息中不会重复包含 Word 文档
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # 显示用户消息
        with st.chat_message("user"):
            st.markdown(user_input)
            if uploaded_file_path:
                st.caption(f"📎 {Path(uploaded_file_path).name}")
        
        # 流式处理AI响应
        # 注意：final_user_input 包含 Word 文档内容（如果有上传文件）
        # 但保存到历史的消息只包含原始输入
        with st.status("Agent 正在思考...", expanded=True) as status:
            try:
                stream = agent_client.astream(
                    message=final_user_input,
                    thread_id=st.session_state.thread_id,
                )
                await draw_messages(stream, is_new=True)
                status.update(label="完成", state="complete")
            except Exception as e:
                st.error(f"Agent 调用异常: {e}")
                status.update(label="错误", state="error")
                log.error(f"Agent 调用异常: {e}", exc_info=True)
        
        st.rerun()


if __name__ == "__main__":
    asyncio.run(main())
