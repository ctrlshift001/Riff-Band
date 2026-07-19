# AI4MS 远程 API 调用说明

> 状态：S0-S9 十阶段工作台基础 API 已实现。OpenAPI `http://localhost:8000/docs` 是当前接口事实；检索任务、Runner 和导出端点将在对应服务接入时扩展。

## 1. 基础地址

```text
http://localhost:8000/api/v1
```

健康检查：`GET /healthz`。领域画像：`GET /api/v1/meta/domain-profile`。十阶段定义：`GET /api/v1/meta/stages`。

## 2. 最小调用流程

### 创建项目

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"title":"生成式AI与企业创新","initial_idea":"生成式AI使用是否提升企业创新绩效？"}'
```

响应包含 `project_id`、`current_stage`、十个 `stages`、审批记录和进度。创建项目时会生成 `problem`（S0）的第一个不可变 revision。

### 列出和读取项目

```bash
curl http://localhost:8000/api/v1/projects
curl http://localhost:8000/api/v1/projects/PROJECT_ID
curl http://localhost:8000/api/v1/projects/PROJECT_ID/stages/current
```

### 生成阶段结构草稿

```bash
curl -X POST http://localhost:8000/api/v1/projects/PROJECT_ID/stages/literature/draft \
  -H "Content-Type: application/json" \
  -d '{"instruction":"建立检索式与纳排标准"}'
```

当前基础实现生成明确标记为 `structure_template` 的结构草稿，不伪装成模型研究结果。接入 Agent 后仍复用同一 revision 接口。

### 保存阶段资产

```bash
curl -X PUT http://localhost:8000/api/v1/projects/PROJECT_ID/stages/problem \
  -H "Content-Type: application/json" \
  -d '{"content":{"research_object":"平台企业","questions":["AI采用如何影响创新？"]},"change_reason":"收窄研究对象","author_type":"human"}'
```

每次保存新增 revision 与 SHA-256 `content_hash`。修改上游阶段会使下游状态失效，但不会删除旧 revision 和审批事件。

### 提交人工决定

```bash
curl -X POST http://localhost:8000/api/v1/projects/PROJECT_ID/stages/problem/decisions \
  -H "Content-Type: application/json" \
  -d '{"decision":"approve","reason":"范围清晰，可以检索","actor_type":"human"}'
```

`decision` 支持 `approve`、`request_changes`、`reject`。只有 `human` 可提交决定；批准后自动解锁下一步。

## 3. 当前基础覆盖

- 创建、读取和列出项目；
- 读取领域画像和十阶段定义；
- 读取当前阶段或指定阶段；
- 生成结构草稿、保存不可变 revision；
- 提交人工审批并推进或阻塞阶段；
- 上游修改后的下游失效；
- SQLite 重启持久化；
- 统一 404、409 和 422 错误；
- GUI、API 和 OpenAPI 共用同一 service 层。

## 4. 后续服务端点

文献多源检索任务、论文卡、研究设计助手、数据/方法卡、Stata BYOL Runner、Claim-Evidence 审核和 HTML/研究包导出将继续挂接在现有 `project_id + stage_key + revision` 契约上。未实现端点不写入当前调用示例，也不能返回伪成功。

API 响应和日志不得包含模型 Key、Stata 许可证或受限原始数据。
