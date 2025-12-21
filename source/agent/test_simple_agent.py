"""
测试简化版多 Agent 测试用例生成系统
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_core.messages import HumanMessage
from source.agent.test_case_simple_agent import agent


def main():
    """运行测试"""
    
    # 示例需求文档
    sample_requirement = """
    用户登录功能需求：
    1. 用户可以通过用户名和密码登录系统
    2. 用户名长度为3-20个字符，只能包含字母、数字和下划线
    3. 密码长度为6-20个字符，必须包含至少一个数字和一个字母
    4. 登录失败3次后，账户将被锁定30分钟
    5. 登录成功后，系统应记录登录时间和IP地址
    6. 支持记住密码功能（可选）
    """
    
    print("="*60)
    print("开始测试多 Agent 测试用例生成系统...")
    print("="*60)
    print(f"\n需求文档：\n{sample_requirement}\n")
    
    # 初始化状态（使用 AgentState 结构）
    from source.agent.test_case_simple_agent import initialize_state
    
    initial_state = initialize_state(max_iterations=3)
    initial_state["messages"] = [HumanMessage(content=f"请根据以下需求文档生成测试用例：\n\n{sample_requirement}")]
    
    config = {"configurable": {"thread_id": "test_001"}}
    
    # 运行流程
    print("\n开始执行 Agent 流程...\n")
    final_state = None
    step_count = 0
    
    try:
        for step in agent.stream(initial_state, config=config, stream_mode="updates"):
            step_count += 1
            for node_name, node_output in step.items():
                print(f"✓ 步骤 {step_count}: 节点 '{node_name}' 执行完成")
                final_state = node_output
        
        print(f"\n流程执行完成，共 {step_count} 个步骤")
        
        # 显示最终结果
        if final_state:
            messages = final_state.get("messages", [])
            print(f"\n✓ 共生成 {len(messages)} 条消息")
            
            # 显示最后几条消息的摘要
            print("\n最后几条消息摘要：")
            for idx, msg in enumerate(messages[-3:], 1):
                if hasattr(msg, 'content'):
                    content = str(msg.content)
                    preview = content[:100] + "..." if len(content) > 100 else content
                    print(f"  {idx}. {preview}")
        
        print("\n" + "="*60)
        print("测试完成！")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

