# AI4MS 前端工作台

本目录包含 AI4MS 的前端实现。

## 新版交互前端

新版界面采用 Next.js、React 与 TypeScript，核心源码位于：

- `app/page.tsx`：科研旅程、阶段智能体、证据库、方法库、Stata Runs 与审批中心；
- `app/globals.css`：深蓝科研操作台与学术衬线字体视觉系统；
- `app/layout.tsx`：页面元信息与全局布局。

本地开发：

```bash
cd src/web
npm ci
npm run dev
```

生产构建：

```bash
npm run build
npm run start
```

## 旧静态原型

`static/` 仍保留现有 FastAPI 直接服务的静态原型，避免本次前端交接破坏后端已有启动路径。待后端正式接入新版前端后，可再统一构建与部署入口。

当前新版页面使用前端 mock 状态演示关键交互，尚未连接真实文献检索、Stata Runner 和审批后端。
