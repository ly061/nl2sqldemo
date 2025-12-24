#!/bin/bash

# 自动部署脚本
# 用于 Jenkins Freestyle 项目自动部署服务

set -e  # 遇到错误立即退出

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 日志文件
LOG_FILE="$SCRIPT_DIR/deploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 日志函数
log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$TIMESTAMP] ERROR: $1" | tee -a "$LOG_FILE" >&2
}

log_success() {
    echo "[$TIMESTAMP] SUCCESS: $1" | tee -a "$LOG_FILE"
}

# 清理函数
cleanup() {
    if [ $? -ne 0 ]; then
        log_error "部署失败，请检查日志: $LOG_FILE"
    fi
}

trap cleanup EXIT

# 开始部署
log "=========================================="
log "开始部署测试用例生成系统"
log "=========================================="

# 检查必要文件是否存在
log "检查必要文件..."
if [ ! -f "$SCRIPT_DIR/stop_services.sh" ]; then
    log_error "未找到 stop_services.sh"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/start_services.sh" ]; then
    log_error "未找到 start_services.sh"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/health_check.sh" ]; then
    log_error "未找到 health_check.sh，将跳过健康检查"
    SKIP_HEALTH_CHECK=true
else
    SKIP_HEALTH_CHECK=false
fi

# 确保脚本有执行权限
log "设置脚本执行权限..."
chmod +x "$SCRIPT_DIR/stop_services.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/start_services.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/health_check.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/run_api.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/run_streamlit.sh" 2>/dev/null || true

# 步骤1: 停止旧服务
log "=========================================="
log "步骤 1/3: 停止旧服务"
log "=========================================="

if [ -f "$SCRIPT_DIR/.api.pid" ] || [ -f "$SCRIPT_DIR/.streamlit.pid" ]; then
    log "发现运行中的服务，正在停止..."
    "$SCRIPT_DIR/stop_services.sh" >> "$LOG_FILE" 2>&1 || {
        log_error "停止服务失败，尝试强制停止..."
        pkill -f "uvicorn api.main:app" 2>/dev/null || true
        pkill -f "streamlit run streamlit_app.py" 2>/dev/null || true
        sleep 2
    }
else
    log "未发现运行中的服务"
fi

# 等待端口释放
log "等待端口释放..."
MAX_WAIT=30
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    API_PORT_IN_USE=$(lsof -ti:9501 2>/dev/null | wc -l)
    STREAMLIT_PORT_IN_USE=$(lsof -ti:8501 2>/dev/null | wc -l)
    
    if [ "$API_PORT_IN_USE" -eq 0 ] && [ "$STREAMLIT_PORT_IN_USE" -eq 0 ]; then
        log "端口已释放"
        break
    fi
    
    sleep 1
    WAITED=$((WAITED + 1))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    log_error "等待端口释放超时，强制释放端口..."
    lsof -ti:9501 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti:8501 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 2
fi

log_success "旧服务已停止"

# 步骤2: 启动新服务
log "=========================================="
log "步骤 2/3: 启动新服务"
log "=========================================="

log "启动所有服务..."
# 直接执行启动脚本（脚本内部已使用 setsid 确保进程脱离会话）
"$SCRIPT_DIR/start_services.sh" >> "$LOG_FILE" 2>&1 || {
    log_error "启动服务失败"
    exit 1
}

# 等待服务启动
log "等待服务启动..."
MAX_WAIT=60
WAITED=0
API_READY=false
STREAMLIT_READY=false

while [ $WAITED -lt $MAX_WAIT ]; do
    # 检查 API 服务
    if ! $API_READY; then
        if curl -s http://localhost:9501/health > /dev/null 2>&1; then
            API_READY=true
            log "API 服务已就绪"
        fi
    fi
    
    # 检查 Streamlit 服务
    if ! $STREAMLIT_READY; then
        if curl -s http://localhost:8501 > /dev/null 2>&1; then
            STREAMLIT_READY=true
            log "Streamlit 服务已就绪"
        fi
    fi
    
    if $API_READY && $STREAMLIT_READY; then
        break
    fi
    
    sleep 2
    WAITED=$((WAITED + 2))
done

if ! $API_READY; then
    log_error "API 服务启动超时"
    exit 1
fi

if ! $STREAMLIT_READY; then
    log_error "Streamlit 服务启动超时"
    exit 1
fi

log_success "所有服务已启动"

# 步骤3: 健康检查
if [ "$SKIP_HEALTH_CHECK" = false ]; then
    log "=========================================="
    log "步骤 3/3: 健康检查"
    log "=========================================="
    
    "$SCRIPT_DIR/health_check.sh" >> "$LOG_FILE" 2>&1 || {
        log_error "健康检查失败"
        exit 1
    }
    
    log_success "健康检查通过"
else
    log "跳过健康检查（health_check.sh 不存在）"
fi

# 部署完成
log "=========================================="
log_success "部署完成！"
log "=========================================="
log ""
log "服务地址："
log "  - 后端 API: http://localhost:9501"
log "  - API 文档: http://localhost:9501/docs"
log "  - 前端界面: http://localhost:8501"
log ""
log "日志文件："
log "  - 部署日志: $LOG_FILE"
log "  - API 日志: $SCRIPT_DIR/api.log"
log "  - Streamlit 日志: $SCRIPT_DIR/streamlit.log"
log ""

exit 0

