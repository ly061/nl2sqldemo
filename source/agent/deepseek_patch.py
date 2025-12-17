"""
补丁文件：修复 langchain-deepseek 1.0.1 中 deepseek-reasoner 模型的 reasoning_content 问题

使用方法：
在导入 ChatDeepSeek 之前导入此文件：
    from source.agent.deepseek_patch import patch_deepseek
    patch_deepseek()
    from langchain_deepseek import ChatDeepSeek
"""


def patch_deepseek():
    """修复 ChatDeepSeek 的 _get_request_payload 方法以支持 reasoning_content"""
    import json
    from langchain_deepseek import ChatDeepSeek
    
    original_get_request_payload = ChatDeepSeek._get_request_payload
    
    def patched_get_request_payload(self, input_, *, stop=None, **kwargs):
        """修复后的 _get_request_payload，支持 reasoning_content"""
        payload = original_get_request_payload(self, input_, stop=stop, **kwargs)
        
        for message in payload["messages"]:
            if message["role"] == "tool" and isinstance(message["content"], list):
                message["content"] = json.dumps(message["content"])
            elif message["role"] == "assistant":
                if isinstance(message["content"], list):
                    # DeepSeek API expects assistant content to be a string, not a list.
                    text_parts = [
                        block.get("text", "")
                        for block in message["content"]
                        if isinstance(block, dict) and block.get("type") == "text"
                    ]
                    message["content"] = "".join(text_parts) if text_parts else ""
                
                # 修复：添加 reasoning_content 支持
                # 如果消息来自 LangChain 的 AIMessage，reasoning_content 可能在 additional_kwargs 中
                # 需要从原始输入中提取
                if hasattr(input_, '__iter__') and not isinstance(input_, (str, dict)):
                    # 尝试从输入消息中提取 reasoning_content
                    for msg in input_:
                        if hasattr(msg, 'additional_kwargs') and 'reasoning_content' in msg.additional_kwargs:
                            message["reasoning_content"] = msg.additional_kwargs["reasoning_content"]
                            break
        
        return payload
    
    ChatDeepSeek._get_request_payload = patched_get_request_payload
    print("✅ DeepSeek reasoning_content patch applied")


if __name__ == "__main__":
    patch_deepseek()

