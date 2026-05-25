# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router.chat_router import router
from service.chat_service import chat_service

app = FastAPI(title="CloudMind API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# FastAPI 启动时初始化 Redis 连接
@app.on_event("startup")
async def startup():
    await chat_service.initialize()
    print("[Main] 服务启动完成")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)