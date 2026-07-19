# AI4MS Docker 部署契约

> 状态：已提供 Dockerfile、Compose、浏览器 GUI 与 API 基础实现；提交前仍须在装有 Docker 的全新机器完成镜像 smoke test。

## 1. 交付形态

最终部署包包含一个主镜像 `ai4ms-workbench:competition`：

- 浏览器 GUI：`http://localhost:8000/`
- 远程 API：`http://localhost:8000/api/v1`
- OpenAPI：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/healthz`

目标容器运行 FastAPI、十阶段 Web 工作台、SQLite 和本地任务执行器。当前 Dockerfile 仍服务兼容静态入口，Next.js 单入口打包尚待发布阶段完成；Stata 不进入镜像，而是由可选外部 BYOL Runner 提供。

## 2. 部署包文件

最终提交至少包含：

```text
Dockerfile
.dockerignore
docker-compose.yml
docs/DEPLOYMENT.md
docs/API_USAGE.md
.env.example
```

## 3. 构建与启动

最终实现必须支持：

```powershell
docker build -t ai4ms-workbench:competition .
docker run --rm `
  -p 8000:8000 `
  --env-file .env `
  -v ai4ms-data:/app/data `
  ai4ms-workbench:competition
```

Compose 启动方式：

```powershell
docker compose up --build
```

服务必须监听 `0.0.0.0:8000`。启动完成后先检查 `/healthz`，再打开根路径使用 GUI。

## 4. 配置与密钥

模型和检索配置沿用 `.env.example` 中的环境变量。真实 `.env` 不得进入 Git、镜像层或部署包。

运行时至少需要：

- 一个可用的 OpenAI-compatible 或 Gemini 模型配置；
- 至少一个开放学术检索后端可联网访问；
- 可选的 Serper 配置；
- 可选的外部 Stata Runner 地址与认证。

未提供模型或检索配置时，服务可以启动并查看已保存项目，但执行相关阶段必须返回明确的 `blocked`，不能生成伪造结果。

## 5. 数据持久化

容器内统一使用 `/app/data`：

```text
/app/data/ai4ms.db
/app/data/projects/<project_id>/artifacts/
/app/data/projects/<project_id>/exports/
```

必须挂载 volume。删除容器后，项目、审批、运行索引和报告仍应保留；删除 volume 才视为删除本地产品数据。

## 6. Stata 运行器

镜像不得包含 Stata 安装文件、许可证、序列号或破解组件。`RunnerService` 通过运行时配置连接用户或机构已有授权环境。

没有 Runner 时：

- 分析计划和 do-file 仍可编辑、保存和预检；
- 正式执行返回 `blocked:no_runner`；
- GUI 明确显示未执行，不展示伪造日志或结果。

## 7. 提交前验证

- 在无 Python 环境的新机器上仅使用 Docker 启动；
- `/healthz`、`/`、`/docs` 和最小项目 API 正常；
- 完成一个十阶段示例项目并重启容器；
- 重启后项目和报告仍存在；
- 检查镜像历史、日志和导出包中没有密钥或许可证；
- 保存一个不依赖现场联网的只读演示项目和 HTML 报告。
