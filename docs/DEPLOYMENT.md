# AI4MS Docker 部署契约

> 状态：已提供 Dockerfile、Compose、浏览器 GUI 与内部后端服务；提交前仍须在装有 Docker 的全新机器完成镜像 smoke test。

## 1. 交付形态

最终部署包包含一个主镜像 `ai4ms-workbench:competition`：

- 浏览器 GUI：`http://localhost:8000/`
- 健康检查：`http://localhost:8000/healthz`

项目没有公网网站。比赛只提交 Docker 部署包，评委在本机启动容器后访问 `http://localhost:8000/`。容器内运行 FastAPI，并由它在同一端口服务 Next.js 静态导出、`/api/v1`、报告下载和健康检查；内部 API 不是第二种交付方式。Stata 不进入镜像，而是由可选外部 BYOL Runner 提供。

## 2. 部署包文件

面向评委的私下交付目录为：

```text
ai4ms-workbench.tar
docker-compose.yml
.env.competition
START_AI4MS.bat
START_AI4MS.ps1
START_AI4MS.sh
SHA256SUMS.txt
BUILD_INFO.txt
DEPLOYMENT.md
AI4MS_AGENT_APPLICATION_DESIGN.html
```

`ai4ms-workbench.tar` 是预构建镜像，`.env.competition` 只保存比赛专用运行时配置。评委不需要源码、Python、Node.js，也不需要手工填写模型 Key。

## 3. 构建与启动

`Dockerfile` 使用三阶段构建：Node 阶段执行 `npm ci` 和 Next.js 静态导出，Python 构建阶段生成干净 wheel，最终阶段只安装运行依赖并复制编译后的网页。最终运行镜像不包含 Node 开发环境、TypeScript 源码、测试或仓库文档。

提交方先在源码根目录准备仅本机存在的 `deployment/competition/.env.competition`，再执行：

```powershell
.\scripts\deployment\BUILD_COMPETITION_PACKAGE.ps1 -ValidateOnly
.\scripts\deployment\BUILD_COMPETITION_PACKAGE.ps1
```

正式构建要求 Git 工作区没有未提交改动，确保镜像内容与 `BUILD_INFO.txt` 中的源码提交号一致。脚本构建镜像并生成 `dist/ai4ms-competition`，同时写入镜像 SHA-256 和源码提交号。真实 Key 不进入源码仓库、Docker 构建上下文或镜像层，只会被复制到最终私下交付目录。

Windows 评委双击：

```powershell
START_AI4MS.bat
```

Linux 或 macOS 评委执行：

```bash
chmod +x START_AI4MS.sh
./START_AI4MS.sh
```

启动脚本会依次校验比赛配置与镜像 SHA-256、加载镜像、启动 Compose、等待 `/healthz`、调用一次真实 LLM 探针和一次容器内 Serper 搜索探针，最后打开 GUI。任一检查失败都会明确停止，不会把“容器已启动”误报为“模型或联网检索可用”。

容器进程监听 `0.0.0.0:8000`，宿主机只把它映射到 `127.0.0.1:8000`。

同一端口的路径约定：

- `/`：Next.js 十阶段科研工作台；
- `/_next/*`、`/favicon.svg`、`/ai4ms-user-guide.html`：前端静态资源；
- `/api/v1/*`：GUI 使用的内部应用接口；
- `POST /api/v1/meta/inference/probe`：发起最小真实模型请求的部署探针；
- `POST /api/v1/meta/search/probe`：从容器内发起真实 Serper 请求的部署探针；
- `/docs`：开发调试用 OpenAPI；
- `/healthz`：容器健康检查。

## 4. 配置与密钥

模型和检索配置沿用 `.env.example` 中的环境变量。开发用 `.env` 和比赛用 `.env.competition` 均不得进入 Git、公开压缩包、可复用镜像层或日志。

为了满足“评委部署后直接使用”，最终私下交付目录可以包含 `.env.competition`，但必须使用单独申请的比赛 Key。该文件对拿到部署包并拥有 Docker 主机权限的人可见，因此需要限制余额与并发，并在评审结束后立即吊销。启动脚本和探针只显示模型名称，不输出 Key。

运行时至少需要：

- 一个可用的 OpenAI-compatible 或 Gemini 模型配置；
- 至少一个开放学术检索后端可联网访问；
- 一个比赛专用的 Serper Key，比赛部署脚本会强制校验并实调；
- 可选的 Google Data Commons MCP key，用于官方统计指标检索；
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

## 6. Stata Local Runner

镜像不得包含 Stata 安装文件、许可证、序列号或破解组件。Docker 中的工作台通过 `host.docker.internal:8765` 连接研究者本机的 `ai4ms-stata-runner`。这条连接只用于同一台机器上的 Docker 与自带许可 Stata，不是比赛要求的公网远程调用接口。

从源码仓库运行安装脚本；它会生成长随机令牌，并同步到本机比赛环境文件：

```powershell
.\scripts\stata-runner\SETUP_STATA_RUNNER.ps1 `
  -StataExecutable "C:\Program Files\Stata18\StataMP-64.exe" `
  -DockerWorkbench
```

然后在研究者本机启动连接器：

```powershell
pip install -e .
.\scripts\stata-runner\START_STATA_RUNNER.ps1
```

然后启动 Docker 工作台：

```powershell
docker compose up --build
```

`0.0.0.0:8765` 是为了让 Docker 虚拟网络访问宿主机服务。必须保留配对令牌，并使用系统防火墙禁止局域网和公网访问该端口。Windows Docker Desktop 通常也可尝试把 `AI4MS_LOCAL_RUNNER_HOST` 改为 `127.0.0.1`；如果容器无法连接，再恢复为 `0.0.0.0`。

运行过程：

1. GUI 上传 `.dta`，工作台保存项目资产、SHA-256、行列数、变量名、标签和格式版本；
2. G3 通过后，工作台生成包含获批 do-file、输入数据、hash 和运行参数的签名 Run Bundle；
3. Local Runner 再次检查令牌、许可、文件 hash 和危险命令，在本机 Stata batch 模式执行；
4. 固定结果脚本导出 `structured_results.csv`、`data_signature.txt`、日志和表图；
5. Local Runner 生成 `result_bundle.json`，只返回允许的聚合结果、日志和表图，不回传 `.dta`；
6. 工作台复核 `run_id`、输入 hash 和 do-file hash 后，将结果登记到 S6，供 S7/S8 使用。

没有 Runner 时：

- 分析计划和 do-file 仍可编辑、保存和预检；
- 正式执行返回 `blocked:no_runner`；
- GUI 明确显示未执行，不展示伪造日志或结果。

完整契约与故障排查见 [Stata 本机连接器](RUNNER.md)。

## 7. 提交前验证

- 在无 Python 环境的新机器上仅使用 Docker 启动；
- `/healthz`、`/` 和 GUI 最小项目流程正常；
- 完成一个十阶段示例项目并重启容器；
- 重启后项目和报告仍存在；
- 检查镜像历史、日志和导出包中没有密钥或许可证；
- 保存一个不依赖现场联网的只读演示项目和 HTML 报告。
- 使用一份无敏感信息的 `.dta` 完成 Docker → Local Runner → Result Bundle → S7/S8 冒烟测试。
