#!/bin/bash

# Streamlit应用启动脚本

echo "🚀 启动测试用例生成系统..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# 检查是否在虚拟环境中
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  未检测到虚拟环境"
    
    # 检查是否存在 .venv 目录
    if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
        echo "✅ 找到虚拟环境，正在自动激活..."
        source "$VENV_DIR/bin/activate"
        echo "✅ 虚拟环境已激活"
    else
        echo "❌ 未找到虚拟环境目录: $VENV_DIR"
        echo "   请先创建虚拟环境: python3 -m venv .venv"
        exit 1
    fi
fi

# 确定 Python 和 pip 命令
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PIP_CMD="pip"
elif [ -f "$VENV_DIR/bin/python" ]; then
    PYTHON_CMD="$VENV_DIR/bin/python"
    PIP_CMD="$VENV_DIR/bin/pip"
else
    echo "❌ Python 未找到"
    exit 1
fi

# 检查 requirements.txt 是否存在
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "❌ 未找到 requirements.txt 文件: $REQUIREMENTS_FILE"
    exit 1
fi

# 每次启动都安装/更新依赖
echo "📦 安装/更新依赖..."
$PIP_CMD install --upgrade pip -q
$PIP_CMD install -r "$REQUIREMENTS_FILE" --upgrade

# 检查 streamlit 命令是否可用
if ! command -v streamlit &> /dev/null; then
    if [ -f "$VENV_DIR/bin/streamlit" ]; then
        echo "✅ 在虚拟环境中找到 streamlit，使用完整路径"
        STREAMLIT_CMD="$VENV_DIR/bin/streamlit"
    else
        echo "❌ streamlit 未安装，请检查 requirements.txt"
        exit 1
    fi
else
    STREAMLIT_CMD="streamlit"
fi

# 启动Streamlit应用
echo ""
echo "🎨 启动Streamlit应用..."
echo "📍 应用地址: http://localhost:8501"
echo ""
echo "💡 提示："
echo "   - 确保 API 服务正在运行 (./run_api.sh)"
echo "   - API 服务默认端口: 9501"
echo "   - 按 Ctrl+C 停止应用"
echo ""

$STREAMLIT_CMD run streamlit_app.py

