# AI4MS 前端工作台

本目录包含 AI4MS 的 Next.js 十阶段科研工作台。

## 新版交互前端

新版界面采用 Next.js、React 与 TypeScript，核心源码位于：

- `app/page.tsx`：S0-S9 科研旅程、阶段资产编辑、证据库、方法库、Stata Runs 与审批中心；
- `app/deep-workspaces.tsx`：项目、草稿、检查整改、决策、论文卡、方法卡、公式卡、审批资产与版本等 L2–L4 页面；
- `app/globals.css`：黑白灰、低饱和蓝与论文纸张三套可切换视觉系统；
- `app/layout.tsx`：页面元信息与全局布局。
- `lib/api.ts`：Next.js 与 FastAPI 的类型化 API 客户端。
- `public/ai4ms-user-guide.html`：面向研究者、审核者和非技术人员的完整产品与使用说明。

先在仓库根目录启动 FastAPI：

```powershell
pip install -e .
ai4ms-web
```

再启动前端：

```bash
cd src/web
npm ci
npm run dev
```

打开 `http://127.0.0.1:3000/`。前端默认请求同源 `/api/v1`，由 `next.config.ts` 代理到 `http://127.0.0.1:8000`。如需修改后端地址：

```powershell
Copy-Item .env.local.example .env.local
```

然后修改 `AI4MS_API_INTERNAL_URL` 并重启 Next.js。

生产构建：

```bash
npm run build
npm run start
```

## 当前连接范围

- 项目创建、列表和切换已连接 SQLite；
- S0-S9 状态、结构草稿、JSON 阶段资产和不可变 revision 已连接 FastAPI；
- S0-S9 模型草稿已连接；S1 支持多源检索与证据综述，S6 支持 Stata Runner 预检和提交运行，S9 支持生成与下载 HTML/ZIP 交付包；
- `approve/request_changes/reject` 人工决定已连接，批准后自动解锁下一阶段；
- 顶层证据库、方法库和 Stata Runs 独立视图仍含演示数据；S0-S9 阶段资产中的检索、方法候选、Run、Claim-Evidence 和交付数据来自真实 API。

## 当前前端能力

- 诊断规则页真实注册并展示 D01–D36，支持家族筛选、全文检索、逐条展开和加入分析计划；
- 右上角用户菜单可在“石墨极简、冷蓝研究、论文纸张”三套偏好中切换，选择保存在浏览器本地；
- “使用说明”直接打开完整 HTML 手册，包含产品介绍、S0–S9、G0–G5、智能体规则、Stata、资产版本、实现结构和 FAQ；
- 资产摘要的六个章节均可下钻查看来源、状态、血缘影响和正文；工作草稿可人工修改，冻结 revision 自动只读；
- 所有深层资产编辑均遵循“智能体建议 → 人工确认 → 同步 → 继续编辑 → 审计留痕”。

本轮仓库核对和验收结果见 [`../../docs/ai4ms/REPOSITORY_AUDIT_2026-07-21.md`](../../docs/ai4ms/REPOSITORY_AUDIT_2026-07-21.md)。

`static/` 是 FastAPI 8000 根路径仍在服务的旧静态兼容入口。开发和演示新版界面应使用 Next.js 的 3000 端口；最终 Docker 统一入口将在发布阶段完成。
