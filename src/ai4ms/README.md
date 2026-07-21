# AI4MS 产品后端

本目录是 AI4MS 比赛产品的统一 Python 命名空间，与仓库中保留的 RiffBand Agent Runtime 和兼容研究引擎分开管理。

## 目录职责

| 目录 | 职责 |
|---|---|
| `api/` | FastAPI 路由、错误映射和服务装配 |
| `services/` | 项目、阶段、审批、模型生成等应用用例 |
| `db/` | SQLite 项目状态、revision 和审批持久化 |
| `domains/` | 管理科学领域画像与稳定领域定义 |
| `inference/` | 模型配置、调用、重试和结构化输出校验 |
| `literature/` | 多源检索、规范化、去重和检索快照 |
| `knowledge/` | 方法库、数据源库及候选项检索 |
| `prompts/` | S0-S9 版本化提示词和 Pydantic 输出契约 |
| `runners/` | Stata BYOL 发现、安全预检、批处理执行和产物 manifest |
| `delivery/` | S9 HTML 可视化报告、manifest、研究 ZIP 包和数据排除策略 |

## 边界规则

- API 只负责 HTTP 协议和依赖装配，业务状态变化进入 `services/`。
- `services/` 可以组合领域、推理、检索、知识和持久化能力。
- `db/` 不调用 API 或前端代码。
- `inference/`、`literature/` 和 `knowledge/` 不写人工审批状态。
- 前端位于 `src/web/`，通过 API 使用产品能力，不直接导入 Python 实现。
- 复用旧研究工具时显式导入 `project/` 或 `research/`，不复制同一实现。

启动入口仍为：

```powershell
ai4ms-web
```
