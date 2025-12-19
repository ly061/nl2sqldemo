#!/bin/bash

# Streamlit应用启动脚本

echo "🚀 启动测试用例生成系统..."

# 检查是否在虚拟环境中
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  未检测到虚拟环境，建议先激活虚拟环境"
    echo "   运行: source venv/bin/activate"
    read -p "是否继续？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检查依赖
echo "📦 检查依赖..."
python -c "import streamlit" 2>/dev/null || {
    echo "❌ Streamlit未安装，正在安装..."
    pip install streamlit
}

# 启动Streamlit应用
echo "🎨 启动Streamlit应用..."
echo "📍 应用地址: http://localhost:8501"
echo ""
echo "💡 提示："
echo "   - 确保LangGraph服务正在运行 (langgraph dev)"
echo "   - 按 Ctrl+C 停止应用"
echo ""

streamlit run streamlit_app.py

