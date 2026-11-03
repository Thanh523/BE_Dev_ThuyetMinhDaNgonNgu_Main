from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config.database import lifespan
from src.config.settings import get_settings
from src.routes import routers


settings = get_settings()
settings.image_storage_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Multilingual Guide API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
for router in routers:
    app.include_router(router)
app.mount(
    "/uploads/images",
    StaticFiles(directory=str(settings.image_storage_dir)),
    name="uploaded-images",
)
