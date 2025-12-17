from langchain.agents import create_agent

from source.agent.llm import llm

def send_email(to: str, subject: str, body: str):

    """
    发送邮件
    :param to: 收件人
    :param subject: 主题
    :param body: 内容
    :return: 发送结果
    """
    print(f"Sending email to {to} with subject {subject} and body {body}")
    return f"Email sent to {to} with subject {subject} and body {body}"


agent = create_agent(
        model=llm,
        tools=[send_email],
        system_prompt="你是一个邮件助手，请使用send_email函数发送邮件"
    )


