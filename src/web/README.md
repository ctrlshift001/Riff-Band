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

- 项目创建、基本信息更新、列表、切换和 SQLite 持久化已连接；
- S0-S9 当前状态、工作区草稿和不可变 revision 已连接 FastAPI；
- 工作区保存使用专用 `PATCH .../workspace` 接口，审批使用真实 human decision 接口；
- 模型草稿、S1 多源检索、S6 Runner 和 S9 HTML/ZIP 导出的 API 客户端与后端路由已经存在，后续逐个替换相应页面中的演示交互；
- 顶层证据库、方法库、Stata Runs、智能体对话和部分审批详情仍含演示数据，不能把这些视图中的示例数字当作真实科研结果。

## 前后端数据契约

- 每个阶段的顶层 `content` 是后端规范对象，例如 S1 的 `papers`、S5 的 `model_specifications`、S8 的 `claims` 和 S9 的 `exports`；
- 新版界面的长文本编辑内容只写入 `content._workspace`，不得使用通用草稿覆盖整个 `content`；
- 工作区 DTO 由 FastAPI/Pydantic 校验，前端保存时必须携带 `expected_revision`；
- revision 不一致时后端返回 `409 revision_conflict`，前端保留本地编辑并要求重新加载合并；
- 项目向导资料保存在 S0 的 `_workspace.project_context`，项目名称与初始问题同时更新到项目记录。

## 当前前端能力

- 诊断规则页真实注册并展示 D01–D36，支持家族筛选、全文检索、逐条展开和加入分析计划；
- 右上角用户菜单可在“石墨极简、冷蓝研究、论文纸张”三套偏好中切换，选择保存在浏览器本地；
- “使用说明”直接打开完整 HTML 手册，包含产品介绍、S0–S9、G0–G5、智能体规则、Stata、资产版本、实现结构和 FAQ；
- 资产摘要的六个章节均可下钻查看来源、状态、血缘影响和正文；工作草稿可人工修改，冻结 revision 自动只读；
- 所有深层资产编辑均遵循“智能体建议 → 人工确认 → 同步 → 继续编辑 → 审计留痕”。

本轮仓库核对和验收结果见 [`../../docs/ai4ms/REPOSITORY_AUDIT_2026-07-21.md`](../../docs/ai4ms/REPOSITORY_AUDIT_2026-07-21.md)。

`static/` 只在没有 Next.js 构建产物时作为旧静态兼容入口。Docker 会将 `out/` 复制到镜像内的 `src/web/dist/`，FastAPI 在 `8000` 端口优先服务新版界面；本地前端开发仍使用 `3000` 端口和 API 重写。
