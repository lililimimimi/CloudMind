# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router.chat_router import router
from service.chat_service import chat_service
from app_config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    await chat_service.initialize()
    print("[Main] 服务启动完成")
    yield
    # 关闭时清理（可选）


app = FastAPI(title="CloudMind API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
