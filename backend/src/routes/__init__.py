from src.routes.activity_routes import router as activity_router
from src.routes.auth_routes import router as auth_router
from src.routes.category_routes import router as category_router
from src.routes.image_routes import router as image_router
from src.routes.place_routes import router as place_router
# Nạp route quản lý user vào danh sách router của ứng dụng.
from src.routes.user_account_routes import router as user_account_router

routers = (
    image_router,
    auth_router,
    activity_router,
    place_router,
    category_router,
    user_account_router,
)

__all__ = ["routers"]