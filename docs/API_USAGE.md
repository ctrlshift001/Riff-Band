# AI4MS 远程 API 调用说明

> 状态：S0-S9 十阶段工作台基础 API 已实现，S1 多源文献检索和 S0-S4 模型草稿已接入。OpenAPI `http://localhost:8000/docs` 是当前接口事实；Runner 和导出端点将在对应服务接入时扩展。

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
  -d '{"instruction":"建立检索式与纳排标准","generation_mode":"model"}'
```

`generation_mode` 支持：

- `model`：S0-S4 调用已配置模型，经过严格 JSON 与引用契约后保存 agent revision；
- `template`：生成明确标记为 `structure_template` 的离线结构模板。

S5-S9 的模型提示词尚未实现，应使用 `template`；请求未实现阶段的 `model` 模式会返回明确的 409，不伪装成模型研究结果。

### 执行 S1 多源检索

先生成并保存 S1 检索计划，再执行：

```bash
curl -X POST http://localhost:8000/api/v1/projects/PROJECT_ID/stages/literature/search \
  -H "Content-Type: application/json" \
  -d '{"backends":["openalex","crossref","semantic_scholar","arxiv"],"limit_per_backend":10,"max_queries":4}'
```

请求也可通过 `queries` 显式指定检索式。服务对各数据源并发检索，以 DOI 优先、标题/首位作者/年份回退去重，保存稳定 `paper_id`、来源与命中检索式，并将原始检索快照写入项目的 `artifacts/literature/`。单个数据源失败时返回部分结果，不丢弃其他来源。

论文保存后再次调用 S1 `draft` 的 `model` 模式，会自动生成基于现有 `paper_id` 的证据综述。

### 查询方法和数据源候选

```bash
curl "http://localhost:8000/api/v1/knowledge/methods?goal=causal&q=企业面板&limit=10"
curl "http://localhost:8000/api/v1/knowledge/data-sources?q=企业专利&limit=12"
```

S3 和 S4 会在服务端自动检索这两个运行时知识库，并拒绝模型输出中的库外 ID。

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
- 读取模型配置状态，使用版本化提示词生成 S0-S4 结构化草稿；
- 执行 OpenAlex、Crossref、Semantic Scholar、arXiv 多源检索、去重和快照；
- 查询 28 项方法与 40 项数据源运行时知识库；
- 读取当前阶段或指定阶段；
- 生成结构草稿、保存不可变 revision；
- 提交人工审批并推进或阻塞阶段；
- 上游修改后的下游失效；
- SQLite 重启持久化；
- 统一 404、409 和 422 错误；
- GUI、API 和 OpenAPI 共用同一 service 层。

## 4. 后续服务端点

论文全文阅读与筛选队列、Stata BYOL Runner、Claim-Evidence 审核和 HTML/研究包导出将继续挂接在现有 `project_id + stage_key + revision` 契约上。未实现端点不写入当前调用示例，也不能返回伪成功。

API 响应和日志不得包含模型 Key、Stata 许可证或受限原始数据。
