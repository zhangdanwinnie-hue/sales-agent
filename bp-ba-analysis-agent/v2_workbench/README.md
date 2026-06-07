# BP BA Agent V2 Workbench

独立 V2 服务，默认入口为 `http://127.0.0.1:8092/`。它不会修改或重启当前 `8091` 版本。

## 启动

```powershell
.\start_v2.ps1
```

脚本会：

- 检查 `8092` 是否已被占用。
- 创建本项目独立 Python 虚拟环境。
- 安装 FastAPI 后端依赖。
- 安装并构建 React/Vite 前端。
- 用 FastAPI 在 `8092` 同时提供 API 和前端页面。

## 自然语言 Agent 配置

右侧对话面板支持双模式：

- 默认 `BPBA_LLM_MODE=auto`：有模型 Key 时走真实 LLM，没有 Key 时走本地规则 Agent。
- `BPBA_LLM_MODE=rule`：强制使用本地规则 Agent，适合无网络演示。
- `BPBA_LLM_MODE=llm`：强制调用 OpenAI 兼容接口。

可选环境变量：

```powershell
$env:BPBA_LLM_MODE="auto"
$env:BPBA_LLM_BASE_URL="https://api.openai.com/v1"
$env:BPBA_LLM_API_KEY="你的 Key"
$env:BPBA_LLM_MODEL="gpt-4.1-mini"
```

无 Key 时仍可直接对话，例如“把维度加上经销商和活动”“新增一个假设：渠道投放质量下降”“基于现在的洞察生成报告”。

## 目录

- `backend/app`：FastAPI、Pydantic 类型、Mock Agent、JSON 持久化和报告导出。
- `frontend/src`：React 工作台、右侧 Agent 对话和模块化过程文档。
- `data/tasks.json`：本地任务状态。
- `exports`：报告导出文件。
