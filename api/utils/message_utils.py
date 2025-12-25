import json
import logging
import uuid
from collections.abc import AsyncGenerator
from langchain_core.messages import (
    AIMessageChunk,
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from typing import Any

from api.schema import ChatMessage, UserInput

logger = logging.getLogger(__name__)


def convert_message_content_to_string(content: str | list[str | dict] | None) -> str:
    """Convert message content to string.
    
    Handles various content formats including:
    - None (common in local model responses)
    - Empty strings
    - String content
    - List of strings or dicts
    """
    # Log the input for debugging
    logger.debug(f"convert_message_content_to_string called with: type={type(content)}, value={repr(content)}")
    
    # Handle None or empty content (common issue with local models)
    if content is None:
        logger.warning("Content is None, returning empty string")
        return ""
    
    if isinstance(content, str):
        logger.debug(f"Content is string: {repr(content)}")
        return content
    
    # Handle empty list
    if not content:
        logger.warning("Content is empty, returning empty string")
        return ""
    
    # Handle list format
    if isinstance(content, list):
        logger.debug(f"Content is list with {len(content)} items")
        text: list[str] = []
        for idx, content_item in enumerate(content):
            logger.debug(f"Processing list item {idx}: type={type(content_item)}, value={repr(content_item)}")
            if isinstance(content_item, str):
                text.append(content_item)
                continue
            if isinstance(content_item, dict):
                # Handle dict with "type": "text" format
                if content_item.get("type") == "text" and "text" in content_item:
                    text.append(str(content_item["text"]))
                # Handle dict with direct "text" key (some local models)
                elif "text" in content_item:
                    text.append(str(content_item["text"]))
                # Handle dict with "content" key (fallback)
                elif "content" in content_item:
                    text.append(str(content_item["content"]))
                else:
                    logger.warning(f"Unknown dict format in content item {idx}: {content_item}")
        result = "".join(text)
        logger.debug(f"Converted list to string: {repr(result)}")
        return result
    
    # Fallback: convert to string
    result = str(content) if content else ""
    logger.warning(f"Unexpected content type {type(content)}, converted to string: {repr(result)}")
    return result


def langchain_to_chat_message(message: BaseMessage) -> ChatMessage:
    """Create a ChatMessage from a LangChain message.
    
    Safely handles None content and other edge cases from local models.
    """
    message_type = message.__class__.__name__
    logger.debug(f"Converting {message_type} to ChatMessage")
    
    # Safely get content, handling None case
    message_content = getattr(message, "content", None)
    logger.debug(f"Original message content: type={type(message_content)}, value={repr(message_content)}")
    
    converted_content = convert_message_content_to_string(message_content)
    logger.debug(f"Converted content: type={type(converted_content)}, value={repr(converted_content)}")
    
    if isinstance(message, HumanMessage):
        chat_msg = ChatMessage(
            type="human",
            content=converted_content,
        )
        logger.debug(f"Created human message: {chat_msg.model_dump()}")
        return chat_msg
    elif isinstance(message, AIMessage):
        ai_message = ChatMessage(
            type="ai",
            content=converted_content,
        )
        if hasattr(message, "tool_calls") and message.tool_calls:
            ai_message.tool_calls = message.tool_calls
            logger.debug(f"AI message has {len(message.tool_calls)} tool calls")
        if hasattr(message, "response_metadata") and message.response_metadata:
            ai_message.response_metadata = message.response_metadata
            logger.debug(f"AI message has response_metadata: {message.response_metadata}")
        
        logger.debug(f"Created AI message: type={ai_message.type}, content_length={len(converted_content)}, has_tool_calls={bool(ai_message.tool_calls)}")
        return ai_message
    elif isinstance(message, ToolMessage):
        chat_msg = ChatMessage(
            type="tool",
            content=converted_content,
            tool_call_id=getattr(message, "tool_call_id", None),
        )
        logger.debug(f"Created tool message: {chat_msg.model_dump()}")
        return chat_msg
    else:
        error_msg = f"Unsupported message type: {message.__class__.__name__}"
        logger.error(error_msg)
        raise ValueError(error_msg)


async def streaming_message_generator(
    user_input: UserInput, agent: CompiledStateGraph
) -> AsyncGenerator[str, None]:
    """
    Generate a stream of messages from the agent.

    This is the workhorse method for the /stream endpoint.
    """
    kwargs = await handle_input(user_input, agent)
    try:
        # Process streamed events from the graph and yield messages over the SSE stream.
        async for stream_event in agent.astream(
            **kwargs,  # type: ignore
            stream_mode=["updates", "messages"],
        ):
            if not isinstance(stream_event, tuple):
                continue
            stream_mode, event = stream_event
            new_messages = []
            if stream_mode == "updates":
                for node, updates in event.items():
                    if node == "__interrupt__":
                        # Handle interrupts if needed
                        continue
                    updates = updates or {}
                    update_messages = updates.get("messages", [])
                    new_messages.extend(update_messages)

            for message in new_messages:
                try:
                    logger.debug(f"Processing message: type={type(message)}, content_type={type(getattr(message, 'content', None))}")
                    chat_message = langchain_to_chat_message(message)
                    logger.debug(f"Converted to ChatMessage: type={chat_message.type}, content={repr(chat_message.content[:50]) if chat_message.content else 'None'}...")
                except Exception as e:
                    logger.error(f"Error parsing message: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Unexpected error'})}\n\n"
                    continue
                # LangGraph re-sends the input message, which feels weird, so drop it
                if (
                    chat_message.type == "human"
                    and chat_message.content == user_input.content
                ):
                    logger.debug("Skipping duplicate human message")
                    continue
                yield f"data: {json.dumps({'type': 'message', 'content': chat_message.model_dump()})}\n\n"

            if stream_mode == "messages":
                msg, _ = event
                # non-LLM nodes will send extra messages, like ToolMessage, we need to drop them.
                if not isinstance(msg, AIMessageChunk):
                    logger.debug(f"Skipping non-AIMessageChunk: {type(msg)}")
                    continue
                content = msg.content
                logger.debug(f"Streaming token: content_type={type(content)}, content={repr(content[:50]) if content else 'None'}...")
                # Handle None, empty string, and other edge cases from local models
                # Empty content in the context of OpenAI usually means
                # that the model is asking for a tool to be invoked.
                # So we only print non-empty content.
                if content is not None:
                    converted_content = convert_message_content_to_string(content)
                    if converted_content:  # Only yield non-empty content
                        logger.debug(f"Yielding token: {repr(converted_content[:50])}...")
                        yield f"data: {json.dumps({'type': 'token', 'content': converted_content})}\n\n"
                    else:
                        logger.debug("Skipping empty converted content")
                else:
                    logger.debug("Skipping None content")
    except Exception as e:
        logger.error(f"Error in message generator: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': 'Internal server error'})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


async def handle_input(
    user_input: UserInput, agent: CompiledStateGraph
) -> dict[str, Any]:
    """
    Parse user input and returns kwargs for agent invocation.
    """
    thread_id = user_input.thread_id or str(uuid.uuid4())

    configurable = {"thread_id": thread_id}

    config = RunnableConfig(configurable=configurable)

    # Check for interrupts that need to be resumed (only if checkpointer is set)
    input: Command | dict[str, Any]
    try:
        state = await agent.aget_state(config=config)
        interrupted_tasks = [
            task for task in state.tasks if hasattr(task, "interrupts") and task.interrupts
        ]
        if interrupted_tasks:
            # assume user input is response to resume agent execution from interrupt
            input = Command(resume=user_input.resume)
        else:
            input = {"messages": [HumanMessage(content=user_input.content)]}
    except ValueError as e:
        # No checkpointer set, just use normal input
        if "No checkpointer set" in str(e):
            input = {"messages": [HumanMessage(content=user_input.content)]}
        else:
            raise

    kwargs = {
        "input": input,
        "config": config,
    }

    return kwargs

