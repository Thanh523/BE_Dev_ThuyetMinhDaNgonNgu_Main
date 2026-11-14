from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.user_auth import require_user
from src.repositories.category_repository import CategoryRepository
from src.repositories.place_repository import PlaceRepository
from src.repositories.user_activity_repository import UserActivityRepository
from src.services.place_service import PlaceService
from src.services.user_activity_service import UserActivityService


router = APIRouter(
    prefix="/api/user",
    tags=["User activity"],
    dependencies=[Depends(require_user)],
)


# Các payload hoạt động chỉ nhận dữ liệu cần thiết, không nhận UserId từ client.
class ListeningCreate(BaseModel):
    audio_id: str = Field(min_length=1, max_length=100)
    played_seconds: int = Field(ge=0, le=2_147_483_647)
    is_completed: bool

    @field_validator("audio_id")
    @classmethod
    def strip_audio_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("AudioId must not be blank.")
        return normalized


class SessionUpdate(BaseModel):
    end_session: bool = False


class UsageEventCreate(BaseModel):
    client_event_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    event_type: str = Field(min_length=1, max_length=100)
    narration_id: int | str | None = None
    audio_id: str | None = Field(default=None, max_length=100)

    @field_validator("client_event_id", "session_id", "event_type")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be blank.")
        return normalized

    @field_validator("audio_id")
    @classmethod
    def strip_optional_audio_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("narration_id")
    @classmethod
    def strip_optional_narration_id(cls, value: int | str | None) -> int | str | None:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None


class PageResponse(BaseModel):
    items: list[dict]
    total: int
    skip: int
    limit: int


def _place_service(database) -> PlaceService:
    settings = get_settings()
    return PlaceService(
        PlaceRepository(database, settings),
        CategoryRepository(database, settings),
        settings.image_storage_dir,
    )


class VisitorSessionView(BaseModel):
    # Hợp đồng response thống nhất LastSeenAt theo ERD.
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="SessionId")
    started_at: datetime = Field(alias="StartedAt")
    last_seen_at: datetime = Field(alias="LastSeenAt")
    ended_at: datetime | None = Field(default=None, alias="EndedAt")


def _service(database) -> UserActivityService:
    # Một service dùng chung cho các luồng hoạt động của user đã xác thực.
    return UserActivityService(UserActivityRepository(database, get_settings()))


@router.get("/places", response_model=PageResponse)
async def list_user_places(
    search: str = Query(default="", max_length=200),
    category_id: int | None = Query(default=None, gt=0),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # User chỉ được duyệt địa điểm đang hiển thị; dữ liệu ẩn vẫn dành cho admin.
    items, total = await _place_service(database).list_places(
        search,
        category_id,
        "visible",
        skip,
        limit,
        True,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/categories")
async def list_user_categories(
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> list[dict]:
    # Trả danh mục chỉ khi có địa điểm hiển thị thuộc danh mục đó.
    return await _service(database).list_visible_categories()


@router.get("/saved-places", response_model=PageResponse)
async def list_saved_places(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Chủ sở hữu luôn lấy từ token, không thể yêu cầu xem danh sách của user khác.
    return await _service(database).list_saved_places(claims["UserId"], skip, limit)


@router.get("/places/{place_id}/audios")
async def list_user_place_audios(
    place_id: int = Path(gt=0),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> list[dict]:
    # Chỉ cung cấp audio đang hoạt động của địa điểm đang hiển thị.
    return await _service(database).list_place_audios(place_id)


@router.get("/places/{place_id}")
async def get_user_place_details(
    place_id: int = Path(gt=0),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Chi tiết chỉ gồm địa điểm đang hiển thị và nội dung được phép cho user.
    return await _service(database).get_place_details(place_id)


@router.post("/saved-places/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def save_place(
    place_id: int = Path(gt=0),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> Response:
    # Chỉ cho lưu địa điểm đang hiển thị; thao tác lặp lại không tạo bản ghi trùng.
    await _service(database).save_place(claims["UserId"], place_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/saved-places/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_place(
    place_id: int = Path(gt=0),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> Response:
    # Chỉ xóa mục lưu thuộc user hiện tại.
    await _service(database).unsave_place(claims["UserId"], place_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/listening-history", response_model=PageResponse)
async def list_listening_history(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Lịch sử nghe được phân trang và luôn lọc theo UserId trong token.
    return await _service(database).list_listening_history(
        claims["UserId"],
        skip,
        limit,
    )


@router.delete("/listening-history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_listening_history(
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> Response:
    # Chỉ xóa lịch sử thuộc tài khoản trong token hiện tại.
    await _service(database).clear_listening_history(claims["UserId"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/listening-history/{history_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_listening_history_entry(
    history_id: str = Path(min_length=1, max_length=128),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> Response:
    # ID bản ghi và UserId cùng nằm trong điều kiện xóa để không đụng user khác.
    await _service(database).delete_listening_history_entry(
        claims["UserId"],
        history_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/listening-history", status_code=status.HTTP_201_CREATED)
async def record_listening(
    request: ListeningCreate,
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Ghi nhận thời lượng và trạng thái hoàn thành sau khi xác thực AudioId.
    return await _service(database).record_listening(
        claims["UserId"],
        request.audio_id,
        request.played_seconds,
        request.is_completed,
    )


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=VisitorSessionView,
)
async def create_session(
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Mỗi phiên mới có ID ngẫu nhiên và thuộc về user đang đăng nhập.
    return await _service(database).create_session(claims["UserId"])


@router.get("/sessions", response_model=PageResponse)
async def list_sessions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # User chỉ xem được các phiên của chính mình.
    return await _service(database).list_sessions(claims["UserId"], skip, limit)


@router.patch("/sessions/{session_id}", response_model=VisitorSessionView)
async def update_session(
    session_id: str,
    request: SessionUpdate,
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Chỉ chủ phiên được cập nhật LastSeenAt hoặc kết thúc phiên đó.
    return await _service(database).touch_session(
        claims["UserId"],
        session_id,
        request.end_session,
    )


@router.post("/usage-events", status_code=status.HTTP_201_CREATED)
async def record_usage_event(
    request: UsageEventCreate,
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Event phải gắn với phiên của user hiện tại; ClientEventId hỗ trợ retry an toàn.
    return await _service(database).record_usage_event(
        claims["UserId"],
        request.client_event_id,
        request.session_id,
        request.event_type,
        request.narration_id,
        request.audio_id,
    )


@router.get("/usage-events", response_model=PageResponse)
async def list_usage_events(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Danh sách event được suy ra từ các session của user, không nhận SessionId để truy vấn.
    return await _service(database).list_usage_events(
        claims["UserId"],
        skip,
        limit,
    )
