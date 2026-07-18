# AI4MS 远程 API 调用契约

> 状态：目标调用契约。实现时以生成的 OpenAPI 为最终接口事实，并同步更新本文示例。

## 1. 基础地址

```text
http://localhost:8000/api/v1
```

交互式接口文档：`http://localhost:8000/docs`。

## 2. 最小调用流程

### 创建项目

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"title":"生成式AI与企业创新","initial_idea":"生成式AI使用是否提升企业创新绩效？"}'
```

响应必须返回 `project_id`、当前步骤和项目状态。

### 提交 TopicBrief

```bash
curl -X POST http://localhost:8000/api/v1/projects/PROJECT_ID/topic-briefs \
  -H "Content-Type: application/json" \
  -d '{"idea":"生成式AI使用是否提升企业创新绩效？","objective":"评估关系、机制与可行设计","approved":true}'
```

### 启动课题侦察

```bash
curl -X POST http://localhost:8000/api/v1/projects/PROJECT_ID/topic-scout-runs \
  -H "Content-Type: application/json" \
  -d '{"depth":"standard"}'
```

长任务返回 `run_id` 和 `queued/running` 状态，不保持 HTTP 请求直到研究完成。

### 查询任务

```bash
curl http://localhost:8000/api/v1/topic-scout-runs/RUN_ID
```

状态使用 `queued/running/needs_input/blocked/failed/succeeded/cancelled`，失败响应包含可操作原因。

### 读取已有研究报告

```bash
curl http://localhost:8000/api/v1/projects/PROJECT_ID/related-research-reports/latest
```

### 保存资产 revision

```bash
curl -X POST http://localhost:8000/api/v1/projects/PROJECT_ID/assets/design-plan/revisions \
  -H "Content-Type: application/json" \
  -d '{"content":{"research_question":"...","assumptions":["..."]},"change_reason":"人工调整识别边界"}'
```

### 提交人工审批

```bash
curl -X POST http://localhost:8000/api/v1/projects/PROJECT_ID/approval-requests \
  -H "Content-Type: application/json" \
  -d '{"gate":"G1","asset_key":"design-plan","revision_id":"REVISION_ID"}'
```

Agent 身份不能批准。六天单用户版本由本地 human actor 执行 `approve/request_changes/reject`。

### Stata 预检

```bash
curl -X POST http://localhost:8000/api/v1/projects/PROJECT_ID/stata-runs/preflight \
  -H "Content-Type: application/json" \
  -d '{"do_file_revision_id":"REVISION_ID","data_asset_id":"DATA_ASSET_ID"}'
```

无外部 Runner 时返回 `blocked:no_runner`，不伪造执行成功。

## 3. API 最低覆盖

远程调用至少覆盖：

- 创建、读取和列出项目；
- 读取当前九步状态；
- 创建 TopicBrief 和启动检索；
- 查询异步任务、错误和产物；
- 读取/创建资产 revision；
- 提交 G0-G5 人工决定；
- Stata preflight、提交、取消和状态；
- 读取 Claim-Evidence；
- 导出 HTML、JSON 和研究包。

## 4. 调用约束

- 所有 ID、时间、状态和错误使用结构化字段；
- 研究、检索和运行任务必须异步；
- API 与 GUI 使用同一 service 层和 SQLite 项目状态；
- `partial/blocked/failed` 不能通过 HTTP 200 包装成业务成功；
- 返回的论文、Claim、Gap 和结果必须携带来源或明确证据状态；
- API 响应和日志不得包含模型 Key、Stata 许可证或受限原始数据。
