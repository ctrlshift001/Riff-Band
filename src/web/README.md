# AI4MS 前端工作台

本目录包含 AI4MS 的 Next.js 十阶段科研工作台。

## 新版交互前端

新版界面采用 Next.js、React 与 TypeScript，核心源码位于：

- `app/page.tsx`：S0-S9 科研旅程、阶段资产编辑、证据库、方法库、Stata Runs 与审批中心；
- `app/globals.css`：深蓝科研操作台与学术衬线字体视觉系统；
- `app/layout.tsx`：页面元信息与全局布局。
- `lib/api.ts`：Next.js 与 FastAPI 的类型化 API 客户端。

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
- S0-S4 模型草稿已连接；S1 支持从界面执行多源检索，并在检索后再次生成证据综述；
- `approve/request_changes/reject` 人工决定已连接，批准后自动解锁下一阶段；
- 证据库、方法库和 Stata Runs 的领域服务仍为演示数据，不能视为已完成后端能力。

`static/` 是 FastAPI 8000 根路径仍在服务的旧静态兼容入口。开发和演示新版界面应使用 Next.js 的 3000 端口；最终 Docker 统一入口将在发布阶段完成。
