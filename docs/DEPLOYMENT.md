# AI4MS Docker 部署契约

> 状态：已提供 Dockerfile、Compose、浏览器 GUI 与内部后端服务；提交前仍须在装有 Docker 的全新机器完成镜像 smoke test。

## 1. 交付形态

最终部署包包含一个主镜像 `ai4ms-workbench:competition`：

- 浏览器 GUI：`http://localhost:8000/`
- 健康检查：`http://localhost:8000/healthz`

项目没有公网网站。比赛只提交 Docker 部署包，评委在本机启动容器后访问 `http://localhost:8000/`。容器内运行 FastAPI，并由它在同一端口服务 Next.js 静态导出、`/api/v1`、报告下载和健康检查；内部 API 不是第二种交付方式。Stata 不进入镜像，而是由可选外部 BYOL Runner 提供。

## 2. 部署包文件

最终提交至少包含：

```text
Dockerfile
.dockerignore
docker-compose.yml
docs/DEPLOYMENT.md
.env.example
```

## 3. 构建与启动

`Dockerfile` 使用两阶段构建：Node 阶段执行 `npm ci` 和 Next.js 静态导出，Python 阶段安装 FastAPI 并复制前端产物。最终运行镜像不包含 Node 开发环境。

构建与启动：

```powershell
docker build -t ai4ms-workbench:competition .
docker run --rm `
  -p 127.0.0.1:8000:8000 `
  --env-file .env `
  -v ai4ms-data:/app/data `
  ai4ms-workbench:competition
```

Compose 启动方式：

```powershell
docker compose up --build
```

容器进程必须监听 `0.0.0.0:8000`，宿主机只把它映射到 `127.0.0.1:8000`。启动完成后先检查 `/healthz`，再打开根路径使用 GUI。

同一端口的路径约定：

- `/`：Next.js 十阶段科研工作台；
- `/_next/*`、`/favicon.svg`、`/ai4ms-user-guide.html`：前端静态资源；
- `/api/v1/*`：GUI 使用的内部应用接口；
- `/docs`：开发调试用 OpenAPI；
- `/healthz`：容器健康检查。

## 4. 配置与密钥

模型和检索配置沿用 `.env.example` 中的环境变量。真实 `.env` 不得进入 Git、镜像层或部署包。

运行时至少需要：

- 一个可用的 OpenAI-compatible 或 Gemini 模型配置；
- 至少一个开放学术检索后端可联网访问；
- 可选的 Serper 配置；
- 可选的 Stata BYOL 批处理可执行文件、版本、许可确认和并发配置。

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

镜像不得包含 Stata 安装文件、许可证、序列号或破解组件。当前 `RunnerService` 发现后端运行环境中由用户或机构合法安装的 Stata 批处理可执行文件；Docker 镜像默认没有 Stata，因此会准确返回 `blocked:no_runner`。需要真实运行时，应在合法授权的本机/机构执行环境启动后端并通过运行时环境变量配置，不能把 Stata 复制进比赛镜像。

没有 Runner 时：

- 分析计划和 do-file 仍可编辑、保存和预检；
- 正式执行返回 `blocked:no_runner`；
- GUI 明确显示未执行，不展示伪造日志或结果。

## 7. 提交前验证

- 在无 Python 环境的新机器上仅使用 Docker 启动；
- `/healthz`、`/` 和 GUI 最小项目流程正常；
- 完成一个十阶段示例项目并重启容器；
- 重启后项目和报告仍存在；
- 检查镜像历史、日志和导出包中没有密钥或许可证；
- 保存一个不依赖现场联网的只读演示项目和 HTML 报告。
