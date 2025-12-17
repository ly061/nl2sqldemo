from langchain_core.output_parsers import SimpleJsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
import os
import json

from source.agent.llm import llm

class People(BaseModel):
    name: str
    age: int

# Improved prompt with clear JSON-only instructions and debugging output
template = (
    "尽你所能回答用户的问题。\n"
    "你必须只以 JSON 格式回答，并且回答必须包含以下字段：\n"
    "  - name（字符串类型）\n"
    "  - age（整数类型）\n"
    "仅输出 JSON，不要添加任何解释或注释。\n"
    "问题：{question}"
)

# Quick check: is the DeepSeek API key present in the environment?
print("DEEPSEEK_API_KEY set:", bool(os.getenv("DEEPSEEK_API_KEY")))

question = "上一届奥运会羽毛球单打冠军是谁"

# Call the LLM directly first to inspect the raw response (helps debug JSONDecodeError)
debug_prompt = template.format(question=question)
try:
    raw = llm.invoke(debug_prompt)
    print("LLM raw response (repr):", repr(raw))
except Exception as e:
    print("Error calling LLM:", e)
    raise

# Try to parse the raw response as JSON to see if the model returned valid JSON
try:
    raw_text = raw if isinstance(raw, str) else str(raw)
    parsed = json.loads(raw_text)
    print("Parsed JSON:", parsed)
except Exception as e:
    print("JSON parse error:", e)

# Now show how to use the prompt + parser chain (keeps original approach) and catch errors
prompt = ChatPromptTemplate.from_template(
    "尽你所能回答用户的问题。\n"
    "你必须只以 JSON 格式回答，并且回答必须包含以下字段：name（字符串），age（整数）。\n"
    "仅输出 JSON，不要添加解释或注释。\n"
    "{question}"
)

chain = prompt | llm | SimpleJsonOutputParser()
try:
    response = chain.invoke(question)
    print("Chain parsed response:", response)
except Exception as e:
    print("Chain error:", e)
