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
from langchain_core.messages import HumanMessage
from source.agent.test_case_simple_agent import agent
from source.agent.utils.log_utils import MyLogger

log = MyLogger().get_logger()

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

# 初始化session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None


def save_uploaded_file(uploaded_file, temp_dir):
    """保存上传的文件到临时目录"""
    file_path = os.path.join(temp_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def process_message(user_input, uploaded_file_path=None):
    """处理用户消息并调用agent"""
    try:
        # 如果有上传的文件，先解析Word文档
        if uploaded_file_path:
            # 直接使用底层函数，避免调用 @tool 装饰的工具对象
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
        
        # 构建消息
        messages = [HumanMessage(content=user_input)]
        
        # 配置thread_id
        if not st.session_state.thread_id:
            import uuid
            st.session_state.thread_id = str(uuid.uuid4())
        
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
        # 调用agent并收集响应
        last_response = ""
        with st.spinner("🤖 AI正在处理，请稍候..."):
            # 使用stream模式获取响应
            for chunk in agent.stream(
                {"messages": messages},
                config=config,
                stream_mode="values"
            ):
                if "messages" in chunk:
                    # 获取所有消息
                    all_messages = chunk["messages"]
                    if all_messages:
                        # 获取最后一条消息（通常是AI的响应）
                        last_msg = all_messages[-1]
                        if hasattr(last_msg, "content") and last_msg.content:
                            # 只保留最新的响应
                            last_response = last_msg.content
        
        # 如果没有响应，尝试获取最后一条消息
        if not last_response:
            # 重新调用一次获取最终结果
            result = agent.invoke({"messages": messages}, config=config)
            if "messages" in result and result["messages"]:
                last_msg = result["messages"][-1]
                if hasattr(last_msg, "content"):
                    last_response = last_msg.content or "未收到响应"
            else:
                last_response = "未收到响应"
        
        response_text = last_response
        
        return response_text
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

# 输入区域布局
input_col1, input_col2, input_col3, input_col4 = st.columns([6, 1, 1, 1])

with input_col1:
    user_input = st.chat_input("Type your message...", key="main_input")

with input_col2:
    st.write("")  # 占位
    # 文件上传按钮
    uploaded_file = st.file_uploader(
        "",
        type=["docx", "doc"],
        key="file_uploader",
        label_visibility="collapsed"
    )
    if uploaded_file:
        st.session_state.uploaded_file = uploaded_file

with input_col3:
    st.write("")  # 占位
    st.write("")  # 占位

with input_col4:
    st.write("")  # 占位
    if st.button("清空", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.session_state.thread_id = None
        st.session_state.uploaded_file = None
        st.rerun()

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
    
    # 处理上传的文件
    uploaded_file_path = None
    if st.session_state.get("uploaded_file"):
        # 创建临时目录保存文件
        temp_dir = tempfile.mkdtemp()
        try:
            uploaded_file_path = save_uploaded_file(st.session_state.uploaded_file, temp_dir)
            # 处理消息
            response = process_message(user_input, uploaded_file_path)
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
        # 处理纯文本消息
        response = process_message(user_input)
    
    # 显示AI响应
    with st.chat_message("assistant"):
        # 检查响应中是否包含Excel文件信息
        excel_filename = extract_excel_filename(response)
        if excel_filename:
            excel_path = Path(__file__).parent / "downloads" / excel_filename
            if excel_path.exists():
                # 添加下载链接到响应中
                download_link = create_download_link(excel_path)
                # 替换或添加下载链接
                if "下载链接" in response or "/api/download" in response:
                    response = re.sub(
                        r'\[点击下载Excel文件\]\([^\)]+\)',
                        download_link,
                        response
                    )
                    response = re.sub(
                        r'/api/download/[^\s\n]+',
                        download_link,
                        response
                    )
                else:
                    response += f"\n\n{download_link}"
        
        st.markdown(response, unsafe_allow_html=True)
    
    # 保存AI消息
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # 重新运行以更新界面
    st.rerun()

# 如果没有消息，显示欢迎信息
if not st.session_state.messages:
    st.markdown("""
    <div style='text-align: center; padding: 4rem 2rem; color: #6b7280;'>
        <p style='font-size: 1.1rem; margin-bottom: 1rem;'>👋 欢迎使用测试用例生成系统</p>
        <p style='font-size: 0.95rem;'>上传Word文档或输入需求描述，系统将自动生成测试用例</p>
    </div>
    """, unsafe_allow_html=True)


