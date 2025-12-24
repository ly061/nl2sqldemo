#!/bin/bash

# 停止所有服务的脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🛑 停止所有服务..."
echo ""

# 停止 API 服务
if [ -f "$SCRIPT_DIR/.api.pid" ]; then
    API_PID=$(cat "$SCRIPT_DIR/.api.pid")
    if ps -p $API_PID > /dev/null 2>&1; then
        kill $API_PID
        echo "✅ 已停止 API 服务 (PID: $API_PID)"
    else
        echo "⚠️  API 服务进程不存在 (PID: $API_PID)"
    fi
    rm -f "$SCRIPT_DIR/.api.pid"
else
    echo "⚠️  未找到 API 服务 PID 文件"
fi

# 停止 Streamlit 服务
if [ -f "$SCRIPT_DIR/.streamlit.pid" ]; then
    STREAMLIT_PID=$(cat "$SCRIPT_DIR/.streamlit.pid")
    if ps -p $STREAMLIT_PID > /dev/null 2>&1; then
        kill $STREAMLIT_PID
        echo "✅ 已停止 Streamlit 服务 (PID: $STREAMLIT_PID)"
    else
        echo "⚠️  Streamlit 服务进程不存在 (PID: $STREAMLIT_PID)"
    fi
    rm -f "$SCRIPT_DIR/.streamlit.pid"
else
    echo "⚠️  未找到 Streamlit 服务 PID 文件"
fi

# 也尝试通过进程名停止（备用方法）
pkill -f "uvicorn api.main:app" 2>/dev/null && echo "✅ 已通过进程名停止 API 服务"
pkill -f "streamlit run streamlit_app.py" 2>/dev/null && echo "✅ 已通过进程名停止 Streamlit 服务"

echo ""
echo "✅ 所有服务已停止"

