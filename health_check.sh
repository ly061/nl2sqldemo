#!/bin/bash

# 健康检查脚本
# 用于检查服务是否正常运行

set -e

# 配置
API_URL="http://localhost:9501"
STREAMLIT_URL="http://localhost:8501"
MAX_RETRIES=3
RETRY_INTERVAL=5

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

log_success() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1"
}

# 检查服务函数
check_service() {
    local name=$1
    local url=$2
    local endpoint=$3
    
    log "检查 $name 服务..."
    
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -s -f --max-time 5 "$url$endpoint" > /dev/null 2>&1; then
            log_success "$name 服务正常"
            return 0
        fi
        
        if [ $i -lt $MAX_RETRIES ]; then
            log "第 $i 次检查失败，${RETRY_INTERVAL}秒后重试..."
            sleep $RETRY_INTERVAL
        fi
    done
    
    log_error "$name 服务检查失败（已重试 $MAX_RETRIES 次）"
    return 1
}

# 开始健康检查
log "=========================================="
log "开始健康检查"
log "=========================================="

# 检查 API 服务
check_service "API" "$API_URL" "/health" || {
    log_error "API 健康检查失败"
    exit 1
}

# 检查 Streamlit 服务
check_service "Streamlit" "$STREAMLIT_URL" "" || {
    log_error "Streamlit 健康检查失败"
    exit 1
}

# 检查端口是否监听
log "检查端口监听状态..."

if lsof -ti:9501 > /dev/null 2>&1; then
    log_success "端口 9501 (API) 正在监听"
else
    log_error "端口 9501 (API) 未监听"
    exit 1
fi

if lsof -ti:8501 > /dev/null 2>&1; then
    log_success "端口 8501 (Streamlit) 正在监听"
else
    log_error "端口 8501 (Streamlit) 未监听"
    exit 1
fi

# 检查进程
log "检查服务进程..."

if pgrep -f "uvicorn api.main:app" > /dev/null; then
    log_success "API 进程运行中"
else
    log_error "API 进程未运行"
    exit 1
fi

if pgrep -f "streamlit run streamlit_app.py" > /dev/null; then
    log_success "Streamlit 进程运行中"
else
    log_error "Streamlit 进程未运行"
    exit 1
fi

log "=========================================="
log_success "所有健康检查通过！"
log "=========================================="

exit 0

