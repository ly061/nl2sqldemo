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


def convert_message_content_to_string(content: str | list[str | dict]) -> str:
    """Convert message content to string."""
    if isinstance(content, str):
        return content
    text: list[str] = []
    for content_item in content:
        if isinstance(content_item, str):
            text.append(content_item)
            continue
        if isinstance(content_item, dict) and content_item.get("type") == "text":
            text.append(content_item["text"])
    return "".join(text)


def langchain_to_chat_message(message: BaseMessage) -> ChatMessage:
    """Create a ChatMessage from a LangChain message."""
    if isinstance(message, HumanMessage):
        return ChatMessage(
            type="human",
            content=convert_message_content_to_string(message.content),
        )
    elif isinstance(message, AIMessage):
        ai_message = ChatMessage(
            type="ai",
            content=convert_message_content_to_string(message.content),
        )
        if hasattr(message, "tool_calls") and message.tool_calls:
            ai_message.tool_calls = message.tool_calls
        if hasattr(message, "response_metadata") and message.response_metadata:
            ai_message.response_metadata = message.response_metadata
        return ai_message
    elif isinstance(message, ToolMessage):
        return ChatMessage(
            type="tool",
            content=convert_message_content_to_string(message.content),
            tool_call_id=message.tool_call_id,
        )
    else:
        raise ValueError(f"Unsupported message type: {message.__class__.__name__}")


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
                    chat_message = langchain_to_chat_message(message)
                except Exception as e:
                    logger.error(f"Error parsing message: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Unexpected error'})}\n\n"
                    continue
                # LangGraph re-sends the input message, which feels weird, so drop it
                if (
                    chat_message.type == "human"
                    and chat_message.content == user_input.content
                ):
                    continue
                yield f"data: {json.dumps({'type': 'message', 'content': chat_message.model_dump()})}\n\n"

            if stream_mode == "messages":
                msg, _ = event
                # non-LLM nodes will send extra messages, like ToolMessage, we need to drop them.
                if not isinstance(msg, AIMessageChunk):
                    continue
                content = msg.content
                if content:
                    # Empty content in the context of OpenAI usually means
                    # that the model is asking for a tool to be invoked.
                    # So we only print non-empty content.
                    yield f"data: {json.dumps({'type': 'token', 'content': convert_message_content_to_string(content)})}\n\n"
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

