# NL2SQL Demo

一个基于 LangChain 和 LangGraph 的自然语言转 SQL 查询的智能助手项目。

## 功能特性

- 🤖 智能 SQL 查询：通过自然语言查询数据库
- 🔍 数据库表结构查询：自动获取数据库表列表和表结构
- ✅ SQL 语法验证：检查 SQL 语句的正确性
- 🛡️ 安全保护：只允许执行 SELECT 查询，防止危险操作

## 技术栈

- LangChain / LangGraph
- DeepSeek API
- SQLAlchemy
- MySQL

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/ly061/nl2sqldemo.git
cd nl2sqldemo
```

2. 创建虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的数据库连接信息和 API 密钥
```

## 使用方法

运行 SQL Agent：
```bash
python source/agent/sql_agent.py
```

## 项目结构

```
langgraphDemo/
├── source/
│   └── agent/
│       ├── sql_agent.py          # SQL Agent 主程序
│       ├── llm.py                # LLM 配置
│       ├── tools/                # 工具集合
│       │   └── tool_sql_table_list.py
│       └── utils/                # 工具函数
│           ├── db_utils.py       # 数据库工具
│           └── log_utils.py      # 日志工具
├── requirements.txt             # 依赖列表
├── .env.example                 # 环境变量模板
└── README.md                    # 项目说明
```

## 环境变量配置

在 `.env` 文件中配置以下变量：

- `DATABASE_URL`: MySQL 数据库连接字符串
- `DEEPSEEK_API_KEY`: DeepSeek API 密钥
- `TAVILY_API_KEY`: Tavily API 密钥（可选）

## License

MIT
