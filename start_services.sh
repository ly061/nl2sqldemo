#!/bin/bash

# 启动所有服务的脚本（后台运行）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 启动所有服务（后台模式）..."
echo ""

# 启动 API 服务（后台，完全脱离会话）
echo "1️⃣ 启动后端 API 服务..."
cd "$SCRIPT_DIR"

# 直接调用 run_api.sh，它内部会处理后台运行和进程脱离
BACKGROUND_MODE=true "$SCRIPT_DIR/run_api.sh" --background

# 等待一下让进程启动并创建 PID 文件
sleep 3

# 从 PID 文件读取实际的进程 ID
if [ -f "$SCRIPT_DIR/.api.pid" ]; then
    API_PID=$(cat "$SCRIPT_DIR/.api.pid")
    # 验证进程是否真的在运行
    if ps -p $API_PID > /dev/null 2>&1; then
        echo "   ✅ API 服务已启动 (PID: $API_PID)"
    else
        echo "   ⚠️  PID 文件存在但进程未运行，尝试查找进程..."
        API_PID=$(pgrep -f "uvicorn api.main:app" | head -1)
        if [ -n "$API_PID" ]; then
            echo "   ✅ API 服务已启动 (PID: $API_PID)"
            echo $API_PID > "$SCRIPT_DIR/.api.pid"
        else
            echo "   ❌ API 服务启动失败，请查看日志: $SCRIPT_DIR/api.log"
            exit 1
        fi
    fi
else
    # 如果 PID 文件不存在，尝试通过进程名查找
    API_PID=$(pgrep -f "uvicorn api.main:app" | head -1)
    if [ -n "$API_PID" ]; then
        echo "   ✅ API 服务已启动 (PID: $API_PID)"
        echo $API_PID > "$SCRIPT_DIR/.api.pid"
    else
        echo "   ❌ API 服务启动失败，请查看日志: $SCRIPT_DIR/api.log"
        exit 1
    fi
fi
echo "   📝 日志文件: $SCRIPT_DIR/api.log"
echo ""

# 等待 API 服务启动
sleep 2

# 启动 Streamlit 服务（后台，完全脱离会话）
echo "2️⃣ 启动 Streamlit 前端服务..."
cd "$SCRIPT_DIR"

# 直接调用 run_streamlit.sh，它内部会处理后台运行和进程脱离
"$SCRIPT_DIR/run_streamlit.sh" --background

# 等待一下让进程启动并创建 PID 文件
sleep 3

# 从 PID 文件读取实际的进程 ID
if [ -f "$SCRIPT_DIR/.streamlit.pid" ]; then
    STREAMLIT_PID=$(cat "$SCRIPT_DIR/.streamlit.pid")
    # 验证进程是否真的在运行
    if ps -p $STREAMLIT_PID > /dev/null 2>&1; then
        echo "   ✅ Streamlit 服务已启动 (PID: $STREAMLIT_PID)"
    else
        echo "   ⚠️  PID 文件存在但进程未运行，尝试查找进程..."
        STREAMLIT_PID=$(pgrep -f "streamlit run streamlit_app.py" | head -1)
        if [ -n "$STREAMLIT_PID" ]; then
            echo "   ✅ Streamlit 服务已启动 (PID: $STREAMLIT_PID)"
            echo $STREAMLIT_PID > "$SCRIPT_DIR/.streamlit.pid"
        else
            echo "   ❌ Streamlit 服务启动失败，请查看日志: $SCRIPT_DIR/streamlit.log"
            exit 1
        fi
    fi
else
    # 如果 PID 文件不存在，尝试通过进程名查找
    STREAMLIT_PID=$(pgrep -f "streamlit run streamlit_app.py" | head -1)
    if [ -n "$STREAMLIT_PID" ]; then
        echo "   ✅ Streamlit 服务已启动 (PID: $STREAMLIT_PID)"
        echo $STREAMLIT_PID > "$SCRIPT_DIR/.streamlit.pid"
    else
        echo "   ❌ Streamlit 服务启动失败，请查看日志: $SCRIPT_DIR/streamlit.log"
        exit 1
    fi
fi
echo "   📝 日志文件: $SCRIPT_DIR/streamlit.log"
echo ""

# 保存 PID 到文件
echo $API_PID > "$SCRIPT_DIR/.api.pid"
echo $STREAMLIT_PID > "$SCRIPT_DIR/.streamlit.pid"

echo "✅ 所有服务已启动！"
echo ""
echo "📍 服务地址："
echo "   - 后端 API: http://localhost:9501"
echo "   - API 文档: http://localhost:9501/docs"
echo "   - 前端界面: http://localhost:8501"
echo ""
echo "💡 管理命令："
echo "   - 查看 API 日志: tail -f $SCRIPT_DIR/api.log"
echo "   - 查看 Streamlit 日志: tail -f $SCRIPT_DIR/streamlit.log"
echo "   - 停止所有服务: ./stop_services.sh"
echo "   - 停止 API: kill $API_PID"
echo "   - 停止 Streamlit: kill $STREAMLIT_PID"
echo ""

