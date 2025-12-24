# Jenkins Freestyle 自动部署配置指南

## 概述

本文档说明如何配置 Jenkins Freestyle 项目来自动部署测试用例生成系统（API + Streamlit）。

## 前置条件

1. **Jenkins 服务器**已安装并运行
2. **SSH 插件**已安装（Publish Over SSH 或 SSH Pipeline Steps）
3. **远程服务器**已配置 SSH 访问权限
4. **项目代码**已部署到远程服务器（无需 Jenkins 拉取代码）

## 部署脚本说明

### 脚本文件

- `deploy.sh` - 主部署脚本，执行完整的部署流程
- `health_check.sh` - 健康检查脚本，验证服务是否正常运行
- `stop_services.sh` - 停止服务脚本
- `start_services.sh` - 启动服务脚本

### 部署流程

```
1. 停止旧服务
   ↓
2. 等待端口释放
   ↓
3. 启动新服务
   ↓
4. 等待服务就绪
   ↓
5. 健康检查
   ↓
6. 部署完成
```

## Jenkins 配置步骤

### 步骤 1: 创建 Freestyle 项目

1. 登录 Jenkins
2. 点击 "新建任务"
3. 输入项目名称：`langgraph-demo-deploy`
4. 选择 "Freestyle project"
5. 点击 "确定"

### 步骤 2: 配置源码管理

**重要**: 由于不需要拉取代码，保持 "None" 选项。

- 源码管理：选择 **None**

### 步骤 3: 配置构建触发器（可选）

根据需要选择：

- **Build periodically**: 定时构建（如：`H 2 * * *` 每天凌晨2点）
- **Build when a change is pushed to GitLab/GitHub**: Git 触发（如果使用）
- **手动触发**: 不配置任何触发器

### 步骤 4: 配置构建环境

#### 方式一：使用 Publish Over SSH 插件

1. 在 "构建环境" 部分，勾选 **Send files or execute commands over SSH**
2. 配置 SSH Server：
   - **SSH Server**: 选择已配置的远程服务器
   - **Credentials**: 选择 SSH 用户名/密钥凭据
   - **Remote directory**: 项目在远程服务器的路径（如：`/opt/langgraphDemo`）

3. **Exec command**（执行命令）:
```bash
cd /opt/langgraphDemo
chmod +x deploy.sh health_check.sh stop_services.sh start_services.sh
./deploy.sh
```

#### 方式二：使用 SSH Pipeline Steps（推荐）

1. 在 "构建" 部分，添加构建步骤：**Execute shell script on remote host using ssh**

2. **SSH Server**: 选择已配置的远程服务器

3. **Command**:
```bash
cd /opt/langgraphDemo
chmod +x deploy.sh health_check.sh stop_services.sh start_services.sh
./deploy.sh
```

### 步骤 5: 配置构建后操作（可选）

#### 5.1 健康检查通知

添加构建后操作：**Send build artifacts over SSH**

- 如果部署失败，可以发送通知邮件或 Slack

#### 5.2 构建通知

添加构建后操作：**Editable Email Notification**

- 配置成功/失败时的邮件通知

### 步骤 6: 保存配置

点击 "保存" 完成配置。

## SSH 服务器配置

### 在 Jenkins 中配置 SSH Server

1. 进入 Jenkins 管理：**Manage Jenkins** → **Configure System**
2. 找到 **Publish over SSH** 部分
3. 点击 **Add** 添加 SSH Server：
   - **Name**: `langgraph-deploy-server`
   - **Hostname**: 远程服务器 IP 或域名
   - **Username**: SSH 用户名
   - **Remote Directory**: 项目根目录（如：`/opt/langgraphDemo`）

4. **Credentials** 配置：
   - 点击 **Add** 添加凭据
   - **Kind**: SSH Username with private key
   - **Username**: SSH 用户名
   - **Private Key**: 粘贴 SSH 私钥内容
   - 或选择 **Use password authentication** 使用密码

5. 点击 **Test Configuration** 测试连接

## 部署脚本路径配置

确保远程服务器上的项目路径与 Jenkins 配置中的路径一致。

**默认路径**: `/opt/langgraphDemo`

如果路径不同，需要修改：
1. Jenkins SSH Server 配置中的 **Remote Directory**
2. 或修改 `deploy.sh` 中的路径变量

## 执行部署

### 手动触发

1. 进入 Jenkins 项目页面
2. 点击 **Build Now**
3. 查看构建日志

### 查看构建日志

1. 点击构建历史中的构建号
2. 点击 **Console Output** 查看详细日志

## 日志文件位置

部署过程中的日志保存在远程服务器：

- **部署日志**: `{项目路径}/deploy.log`
- **API 日志**: `{项目路径}/api.log`
- **Streamlit 日志**: `{项目路径}/streamlit.log`

## 故障排查

### 1. SSH 连接失败

- 检查 SSH 服务器配置是否正确
- 测试 SSH 连接：`ssh user@hostname`
- 检查防火墙设置

### 2. 权限错误

- 确保脚本有执行权限：`chmod +x *.sh`
- 确保 Jenkins 用户有项目目录的读写权限

### 3. 服务启动失败

- 查看部署日志：`tail -f deploy.log`
- 查看服务日志：`tail -f api.log` 或 `tail -f streamlit.log`
- 检查端口是否被占用：`lsof -i:9501` 或 `lsof -i:8501`

### 4. 健康检查失败

- 检查服务是否正常启动：`ps aux | grep -E "(uvicorn|streamlit)"`
- 手动执行健康检查：`./health_check.sh`
- 检查网络连接和防火墙

### 5. 虚拟环境问题

- 确保虚拟环境已创建：`python3 -m venv .venv`
- 检查虚拟环境路径是否正确

## 高级配置

### 环境变量配置

如果需要设置环境变量，可以在 `deploy.sh` 中添加：

```bash
export PORT=9501
export HOST=0.0.0.0
```

### 多环境部署

可以为不同环境创建不同的 Jenkins 项目：

- `langgraph-demo-deploy-dev` - 开发环境
- `langgraph-demo-deploy-prod` - 生产环境

每个项目配置不同的：
- SSH Server（不同的服务器）
- Remote Directory（不同的路径）
- 环境变量

### 回滚机制

如果部署失败，可以添加回滚步骤：

1. 在构建后操作中添加条件判断
2. 如果健康检查失败，执行回滚脚本
3. 恢复之前的服务版本

## 示例配置

### 完整的 Exec Command

```bash
#!/bin/bash
set -e

# 项目路径
PROJECT_DIR="/opt/langgraphDemo"
cd "$PROJECT_DIR"

# 设置权限
chmod +x deploy.sh health_check.sh stop_services.sh start_services.sh

# 执行部署
./deploy.sh

# 检查部署结果
if [ $? -eq 0 ]; then
    echo "部署成功"
    exit 0
else
    echo "部署失败"
    exit 1
fi
```

## 注意事项

1. **不要拉取代码**: Jenkins 配置中源码管理选择 "None"
2. **路径一致性**: 确保 Jenkins 配置的路径与服务器实际路径一致
3. **权限问题**: 确保 Jenkins 用户有执行脚本的权限
4. **日志查看**: 部署失败时查看 `deploy.log` 获取详细信息
5. **端口冲突**: 部署前确保端口 9501 和 8501 可用
6. **进程脱离**: 脚本使用 `setsid` 确保服务进程完全脱离 Jenkins 会话，Jenkins job 结束后服务仍会继续运行

## 进程脱离机制

为了解决 Jenkins job 结束后服务被终止的问题，脚本采用了以下机制：

1. **跨平台兼容**:
   - **Linux 系统**: 使用 `setsid` 创建新的会话组，完全脱离当前会话
   - **macOS 系统**: 使用 `nohup` + `disown` 让进程脱离当前 shell
   - 脚本会自动检测系统并选择合适的方式

2. **重定向 stdin**: 将 stdin 重定向到 `/dev/null`，确保进程完全后台运行
3. **nohup**: 忽略挂起信号（SIGHUP）
4. **后台运行**: 所有服务进程都在后台运行，不阻塞 Jenkins job
5. **进程验证**: 启动后验证进程是否真的在运行，失败时显示错误日志

这样即使 Jenkins job 结束，服务进程也会继续运行。

## 相关文件

- `deploy.sh` - 主部署脚本
- `health_check.sh` - 健康检查脚本
- `start_services.sh` - 启动服务脚本
- `stop_services.sh` - 停止服务脚本
- `SERVICES.md` - 服务管理文档

