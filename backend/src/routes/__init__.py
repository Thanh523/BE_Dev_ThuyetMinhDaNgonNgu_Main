from src.routes.activity_routes import router as activity_router
from src.routes.auth_routes import router as auth_router
from src.routes.category_routes import router as category_router
from src.routes.image_routes import router as image_router
from src.routes.audio_routes import router as audio_router
from src.routes.place_routes import router as place_router
# Nạp route quản lý user vào danh sách router của ứng dụng.
from src.routes.user_account_routes import router as user_account_router
from src.routes.narration_routes import router as narration_router
from src.routes.user_auth_routes import router as user_auth_router
from src.routes.user_activity_routes import router as user_activity_router

routers = (
    image_router,
    audio_router,
    auth_router,
    activity_router,
    place_router,
    category_router,
    user_account_router,
    user_auth_router,
    user_activity_router,
    narration_router,
)

__all__ = ["routers"]