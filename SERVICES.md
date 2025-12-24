# 服务启动和管理指南

## 快速开始

### 一键启动所有服务（后台运行）

```bash
./start_services.sh
```

这会启动：
- 后端 API 服务（端口 9501）
- Streamlit 前端服务（端口 8501）

### 停止所有服务

```bash
./stop_services.sh
```

## 单独启动服务

### 启动后端 API（前台运行）

```bash
./run_api.sh
```

### 启动后端 API（后台运行）

```bash
nohup ./run_api.sh > api.log 2>&1 &
```

### 启动 Streamlit（前台运行）

```bash
./run_streamlit.sh
```

### 启动 Streamlit（后台运行）

```bash
./run_streamlit.sh --background
# 或
./run_streamlit.sh -b
```

## 服务地址

- **后端 API**: http://localhost:9501
- **API 文档**: http://localhost:9501/docs
- **前端界面**: http://localhost:8501

## 日志管理

### 查看 API 日志

```bash
tail -f api.log
```

### 查看 Streamlit 日志

```bash
tail -f streamlit.log
```

## 进程管理

### 查看运行中的服务

```bash
ps aux | grep -E "(uvicorn|streamlit)" | grep -v grep
```

### 通过 PID 停止服务

PID 文件保存在项目根目录：
- `.api.pid` - API 服务进程 ID
- `.streamlit.pid` - Streamlit 服务进程 ID

```bash
# 停止 API
kill $(cat .api.pid)

# 停止 Streamlit
kill $(cat .streamlit.pid)
```

### 通过进程名停止服务

```bash
# 停止 API
pkill -f "uvicorn api.main:app"

# 停止 Streamlit
pkill -f "streamlit run streamlit_app.py"
```

## 常见问题

### 端口被占用

如果端口被占用，可以：

1. 停止占用端口的进程：
```bash
lsof -ti:9501 | xargs kill -9  # API 端口
lsof -ti:8501 | xargs kill -9  # Streamlit 端口
```

2. 或修改端口：
```bash
PORT=9502 ./run_api.sh  # 修改 API 端口
```

### 服务无法启动

1. 检查虚拟环境是否激活
2. 检查依赖是否安装：`pip install -r requirements.txt`
3. 查看日志文件排查错误

### 后台服务无法访问

1. 检查服务是否正在运行：`ps aux | grep streamlit`
2. 检查端口是否监听：`lsof -i:8501`
3. 查看日志文件：`tail -f streamlit.log`

