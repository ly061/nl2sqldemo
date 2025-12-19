# Streamlit 前端应用使用说明

## 功能特性

- 📤 **Word文档上传**：支持上传 `.docx` 和 `.doc` 格式的Word文档
- 💬 **对话交互**：与AI助手进行自然语言对话
- 📊 **测试用例生成**：自动生成测试用例并评审
- 📥 **Excel下载**：生成的测试用例可下载为Excel文件
- 📝 **对话历史**：保存并显示对话历史记录

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动应用

### 方式1：直接运行Streamlit应用

```bash
streamlit run streamlit_app.py
```

### 方式2：同时运行LangGraph服务和Streamlit应用

**终端1 - 启动LangGraph服务：**
```bash
langgraph dev
```

**终端2 - 启动Streamlit应用：**
```bash
streamlit run streamlit_app.py
```

应用将在浏览器中自动打开，默认地址：`http://localhost:8501`

## 使用流程

1. **上传Word文档**（可选）
   - 在左侧边栏点击"上传Word文档"
   - 选择 `.docx` 或 `.doc` 格式的文件

2. **输入需求**
   - 在底部输入框中输入需求描述
   - 如果已上传Word文档，系统会自动解析文档内容

3. **生成测试用例**
   - 点击发送后，系统会自动：
     - 解析Word文档（如果已上传）
     - 生成测试用例
     - 评审测试用例质量
     - 生成Excel文件

4. **下载Excel文件**
   - 生成完成后，可以在左侧边栏下载Excel文件
   - 或者在对话中直接点击下载按钮

## 界面说明

### 主界面
- **对话区域**：显示用户和AI的对话历史
- **输入框**：输入需求描述
- **清空对话**：清除当前对话历史

### 侧边栏
- **文件上传**：上传Word文档
- **生成的Excel文件**：显示所有生成的Excel文件列表
- **刷新文件列表**：更新Excel文件列表
- **使用说明**：查看使用帮助

## 注意事项

1. **LangGraph服务**：确保LangGraph服务正在运行（`langgraph dev`）
2. **文件存储**：生成的Excel文件保存在 `downloads/` 目录
3. **对话历史**：刷新页面会清空对话历史（除非使用session state持久化）

## 故障排除

### 问题1：无法连接到LangGraph服务
- 确保 `langgraph dev` 正在运行
- 检查端口是否被占用

### 问题2：Word文档解析失败
- 确保文件格式正确（`.docx` 或 `.doc`）
- 检查文件是否损坏

### 问题3：Excel文件无法下载
- 检查 `downloads/` 目录是否存在
- 确认文件已成功生成

## 技术栈

- **前端框架**：Streamlit
- **后端服务**：LangGraph + LangChain
- **文件处理**：python-docx, openpyxl
- **AI模型**：DeepSeek Chat

