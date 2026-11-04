from src.routes.activity_routes import router as activity_router
from src.routes.auth_routes import router as auth_router
from src.routes.category_routes import router as category_router
from src.routes.image_routes import router as image_router
from src.routes.audio_routes import router as audio_router
from src.routes.place_routes import router as place_router

routers = (
    image_router,
    audio_router,
    auth_router,
    activity_router,
    place_router,
    category_router,
)

__all__ = ["routers"]