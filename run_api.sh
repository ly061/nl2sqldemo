#!/bin/bash
# 启动 API 服务器

echo "🚀 启动测试用例生成 API 服务..."

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

# 确定 pip 命令
if command -v pip &> /dev/null; then
    PIP_CMD="pip"
elif [ -f "$VENV_DIR/bin/pip" ]; then
    PIP_CMD="$VENV_DIR/bin/pip"
else
    echo "❌ pip 未找到"
    exit 1
fi

# 确定 python 命令
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
elif [ -f "$VENV_DIR/bin/python" ]; then
    PYTHON_CMD="$VENV_DIR/bin/python"
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

# 检查 uvicorn 是否可用
if ! command -v uvicorn &> /dev/null; then
    if [ -f "$VENV_DIR/bin/uvicorn" ]; then
        echo "✅ 在虚拟环境中找到 uvicorn，使用完整路径"
        UVICORN_CMD="$VENV_DIR/bin/uvicorn"
    else
        echo "❌ uvicorn 未安装，请检查 requirements.txt"
        exit 1
    fi
else
    UVICORN_CMD="uvicorn"
fi

# 默认使用 9000 端口
PORT=${PORT:-9000}

# 启动 FastAPI 应用
echo ""
echo "📍 API 地址: http://localhost:$PORT"
echo "📖 API 文档: http://localhost:$PORT/docs"
echo ""
echo "💡 提示："
echo "   - 默认使用 9000 端口"
echo "   - 可通过 PORT 环境变量修改端口: PORT=9001 ./run_api.sh"
echo "   - 按 Ctrl+C 停止服务"
echo ""

$UVICORN_CMD api.main:app --host 0.0.0.0 --port $PORT --reload

