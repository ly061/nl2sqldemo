"""
消息转换器
用于将文件类型的消息内容转换为文本，以兼容不支持multimodal的LLM（如DeepSeek）
"""
import base64
import tempfile
from pathlib import Path
from typing import List, Any
from langchain_core.messages import BaseMessage, HumanMessage
from source.agent.tools.tool_word_parser import _parse_word_from_path
from source.agent.utils.log_utils import MyLogger

log = MyLogger().get_logger()


def convert_file_messages_to_text(messages: List[BaseMessage]) -> List[BaseMessage]:
    """将消息中的文件内容转换为文本
    
    检测HumanMessage中的file类型内容块，如果是Word文档则解析为文本
    
    Args:
        messages: 消息列表
    
    Returns:
        转换后的消息列表
    """
    converted_messages = []
    
    for message in messages:
        if isinstance(message, HumanMessage):
            # 检查消息内容
            if isinstance(message.content, list):
                text_parts = []
                file_info = []
                
                for content_block in message.content:
                    if isinstance(content_block, dict):
                        content_type = content_block.get("type")
                        
                        if content_type == "text":
                            # 保留文本内容
                            text_parts.append(content_block.get("text", ""))
                        
                        elif content_type == "file":
                            # 处理文件内容
                            mime_type = content_block.get("mimeType", "")
                            data = content_block.get("data")
                            filename = content_block.get("metadata", {}).get("filename", "unknown")
                            
                            # 检查是否是Word文档
                            if mime_type in [
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                "application/msword"
                            ]:
                                try:
                                    # 解码base64数据
                                    file_data = base64.b64decode(data)
                                    
                                    # 创建临时文件
                                    suffix = '.docx' if 'openxml' in mime_type else '.doc'
                                    temp_file = tempfile.NamedTemporaryFile(
                                        delete=False,
                                        suffix=suffix,
                                        prefix='word_'
                                    )
                                    temp_file.write(file_data)
                                    temp_file.close()
                                    
                                    doc_path = Path(temp_file.name)
                                    
                                    # 解析Word文档
                                    paragraphs, tables_content = _parse_word_from_path(doc_path)
                                    
                                    # 组合内容
                                    content_parts = []
                                    if paragraphs:
                                        content_parts.append("\n".join(paragraphs))
                                    if tables_content:
                                        content_parts.append("\n\n表格内容：\n" + "\n\n".join(tables_content))
                                    
                                    word_content = "\n\n".join(content_parts) if content_parts else ""
                                    
                                    # 添加到文本部分
                                    text_parts.append(f"\n\n[Word文档内容 - {filename}]\n{word_content}\n")
                                    
                                    # 清理临时文件
                                    try:
                                        doc_path.unlink(missing_ok=True)
                                    except Exception as e:
                                        log.warning(f"清理临时文件失败: {e}")
                                    
                                    log.info(f"成功解析Word文档: {filename}")
                                    
                                except Exception as e:
                                    error_msg = f"解析Word文档失败: {str(e)}"
                                    log.error(error_msg)
                                    text_parts.append(f"\n\n[错误：无法解析Word文档 {filename}: {error_msg}]\n")
                            
                            elif mime_type == "application/pdf":
                                # PDF文件，提示用户需要文本内容
                                text_parts.append(f"\n\n[提示：检测到PDF文件 {filename}，请提供文本内容或使用支持PDF的LLM]\n")
                            
                            else:
                                # 其他文件类型
                                file_info.append(f"文件: {filename} (类型: {mime_type})")
                        
                        elif content_type == "image":
                            # 图片文件，提示用户需要文本描述
                            image_name = content_block.get("metadata", {}).get("name", "unknown")
                            text_parts.append(f"\n\n[提示：检测到图片文件 {image_name}，请提供图片的文字描述]\n")
                
                # 如果有文件信息，添加到文本中
                if file_info:
                    text_parts.append(f"\n[上传的文件: {', '.join(file_info)}]\n")
                
                # 创建新的HumanMessage，只包含文本内容
                if text_parts:
                    new_content = "\n".join(text_parts)
                    converted_message = HumanMessage(content=new_content)
                    # 保留原始消息的其他属性
                    converted_message.id = message.id
                    converted_message.additional_kwargs = message.additional_kwargs
                    converted_messages.append(converted_message)
                else:
                    # 如果没有文本内容，保留原消息
                    converted_messages.append(message)
            else:
                # 内容不是列表，直接保留
                converted_messages.append(message)
        else:
            # 非HumanMessage，直接保留
            converted_messages.append(message)
    
    return converted_messages

