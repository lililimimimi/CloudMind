# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router.chat_router import router

app = FastAPI(title="CloudMind API")

# CORS 配置，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 开发阶段先放开所有来源
    allow_credentials=True,
    allow_methods=["*"],        # 允许所有方法包括 OPTIONS
    allow_headers=["*"],        # 允许所有请求头
)

app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)