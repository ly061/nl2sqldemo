"""
LLM包装器
用于在调用LLM之前自动转换文件消息为文本
"""
from typing import Any, List, Optional, Iterator, AsyncIterator
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from pydantic import Field
from source.agent.utils.message_converter import convert_file_messages_to_text
from source.agent.llm import llm as base_llm


class FileMessageConverterLLM(BaseChatModel):
    """包装LLM，自动将文件消息转换为文本"""
    
    base_model: BaseChatModel = Field(..., description="基础LLM模型")
    
    def __init__(self, base_model: BaseChatModel, **kwargs):
        super().__init__(base_model=base_model, **kwargs)
    
    @property
    def _llm_type(self) -> str:
        return f"FileMessageConverter({self.base_model._llm_type})"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        # 转换消息
        converted_messages = convert_file_messages_to_text(messages)
        # 调用基础LLM
        return self.base_model._generate(converted_messages, stop=stop, run_manager=run_manager, **kwargs)
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        # 转换消息
        converted_messages = convert_file_messages_to_text(messages)
        # 调用基础LLM
        return await self.base_model._agenerate(converted_messages, stop=stop, run_manager=run_manager, **kwargs)
    
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGeneration]:
        # 转换消息
        converted_messages = convert_file_messages_to_text(messages)
        # 调用基础LLM
        return self.base_model._stream(converted_messages, stop=stop, run_manager=run_manager, **kwargs)
    
    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGeneration]:
        # 转换消息
        converted_messages = convert_file_messages_to_text(messages)
        # 调用基础LLM
        async for chunk in self.base_model._astream(converted_messages, stop=stop, run_manager=run_manager, **kwargs):
            yield chunk
    
    def bind_tools(self, tools, **kwargs):
        return self.base_model.bind_tools(tools, **kwargs)
    
    def with_structured_output(self, schema, **kwargs):
        return self.base_model.with_structured_output(schema, **kwargs)


# 创建包装后的LLM实例
llm = FileMessageConverterLLM(base_llm)

