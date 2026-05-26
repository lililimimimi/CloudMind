# CloudMind Frontend

`frontend/` 是 CloudMind 的聊天前端，使用 React + TypeScript + Vite 构建。它提供企业云智能客服界面，支持新对话、历史对话、典型场景快捷提问、SSE 流式回答展示、Markdown 图片和链接渲染。

## 主要功能

- CloudMind 品牌侧边栏
- 新建对话和本地历史对话切换
- 欢迎页典型场景快捷入口
- 聊天输入框，支持 Enter 发送、Shift + Enter 换行
- 调用后端 `POST /api/chat`
- 读取 `text/event-stream` 流式响应
- 逐字追加 assistant 回复
- 渲染 Markdown 链接和图片
- 加载态和打字光标效果

## 技术栈

- React 19
- TypeScript
- Vite
- Ant Design
- Ant Design Icons
- Lucide React

## 目录结构

```text
frontend/
├── public/
│   ├── cloudmind-logo.svg
│   ├── favicon.svg
│   └── logo-options/
├── src/
│   ├── components/
│   │   ├── ChatWindow.tsx      # 聊天主界面和请求逻辑
│   │   ├── Sidebar.tsx         # 侧边栏与历史对话
│   │   ├── WelcomeScreen.tsx   # 欢迎页和快捷问题
│   │   ├── MessageList.tsx     # 消息列表和内容渲染
│   │   └── InputBar.tsx        # 输入框
│   ├── App.tsx
│   ├── index.css
│   └── main.tsx
├── index.html
├── package.json
└── vite.config.ts
```

## 安装依赖

```bash
cd frontend
npm install
```

## 本地启动

```bash
npm run dev
```

默认地址：

```text
http://localhost:5173
```

前端默认请求：

```text
http://localhost:8000/api/chat
```

可通过 `.env` 覆盖：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_DEMO_USER_ID=user_1001
```

因此启动前端前，请先确保后端服务运行在 `localhost:8000`。

## 可用命令

```bash
npm run dev      # 启动开发服务器
npm run build    # TypeScript 构建检查并打包
npm run lint     # ESLint 检查
npm run preview  # 预览生产构建
```

## 请求协议

`ChatWindow.tsx` 中的 `handleSend` 会向后端发送：

```json
{
  "query": "用户输入的问题",
  "user_id": "user_1001",
  "session_id": "session_001"
}
```

后端返回 SSE：

```text
data: {"content":"回答片段"}

data: {"done":true}
```

前端会读取 `ReadableStream`，解析每一行 `data: `，并把 `content` 追加到最后一条 assistant 消息中。

## 关键组件

### `ChatWindow.tsx`

聊天主容器，维护：

- `messages`
- `loading`
- `conversations`
- `sessionId`

同时负责调用后端接口和处理 SSE 响应。

### `WelcomeScreen.tsx`

展示四类典型场景：

- 产品咨询与推荐
- 账单与实例查询
- 资源优化与降本
- 产品推广活动

点击快捷问题会直接发送到后端。

### `MessageList.tsx`

负责渲染用户和 assistant 消息，并额外支持：

- `![alt](url)` 图片渲染
- `[text](url)` 链接渲染
- assistant 空内容时的思考动画
- assistant 流式输出时的光标效果

### `InputBar.tsx`

聊天输入区：

- Enter：发送
- Shift + Enter：换行
- loading 时禁用发送

### `Sidebar.tsx`

侧边栏：

- 展示 CloudMind logo
- 新对话按钮
- 本地历史对话列表
- 当前演示用户 `user_1001`

## 联调注意事项

- 当前 `user_id` 固定为 `user_1001`，适合配合 `mock_data/init.sql` 中的模拟数据测试。
- 历史对话只保存在浏览器内存中，刷新页面会丢失。
- 后端地址通过 `VITE_API_BASE_URL` 配置，默认值是 `http://localhost:8000`。
- 当前 SSE 解析按换行切分，后端保持 `data: {...}\n\n` 格式即可。
- 图片和链接渲染只支持简单 Markdown 语法，不是完整 Markdown 解析器。

## 常见问题

### 页面能打开，但发送后没有回复

检查后端是否启动：

```text
http://localhost:8000
```

并查看浏览器控制台是否有网络或 CORS 错误。

### 账单类问题没有数据

前端默认用户是 `user_1001`。确认后端和 Agent 已连接 MySQL，并导入了 `mock_data/init.sql`。

### 想改后端地址

当前地址可通过 `.env` 配置：

```env
VITE_API_BASE_URL=https://your-api.example.com
```
