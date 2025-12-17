from source.agent.llm import llm


resp = llm.invoke("请用三句话介绍一下机器学习")

print(type(resp))
print(resp)