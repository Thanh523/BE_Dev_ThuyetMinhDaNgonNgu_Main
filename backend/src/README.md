# Hướng dẫn đọc mã nguồn Backend

Tài liệu này là bản đồ để lần theo chức năng trong `src`. API được xây dựng
bằng FastAPI, dùng MongoDB; phần lớn chức năng đi theo luồng:

```text
Request HTTP -> routes -> controllers -> services -> repositories -> MongoDB
                                      |             |
                              kiểm tra request   nghiệp vụ, kiểm tra dữ liệu,
                              và trả response    gọi repository, xử lý lỗi
```

`routes` chủ yếu gom và đăng ký router; logic endpoint thật nằm trong
`controllers`. Một số controller khởi tạo service/repository ngay trong file
để kết nối các lớp cho request hiện tại.

## Bắt đầu từ đâu?

- [`main.py`](./main.py): tạo ứng dụng FastAPI, bật CORS, đăng ký toàn bộ router
  và mở thư mục upload dưới các URL `/uploads/images` và `/uploads/audio`.
- [`routes/__init__.py`](./routes/__init__.py): danh sách router được đưa vào
  ứng dụng. Muốn một nhóm API hoạt động, router của nhóm đó phải được đăng ký ở
  đây.
- [`config/settings.py`](./config/settings.py): đọc cấu hình MongoDB, JWT,
  CORS, đường dẫn lưu file, giới hạn upload, thời gian xác định user online và
  khóa DeepL từ biến môi trường/tệp cấu hình.
- [`config/database.py`](./config/database.py): mở kết nối MongoDB khi ứng dụng
  khởi động, tạo index và dữ liệu ngôn ngữ mặc định; cung cấp database cho
  endpoint qua `get_database`.
- [`create_admin.py`](./create_admin.py): tiện ích dòng lệnh tạo tài khoản
  admin đầu tiên.

## Chức năng theo nhóm

### API và xác thực

| Nhóm | Controller | Service | Repository | Vai trò |
| --- | --- | --- | --- | --- |
| Đăng nhập admin | [`controllers/auth_controller.py`](./controllers/auth_controller.py) | [`services/admin_auth_service.py`](./services/admin_auth_service.py) | [`repositories/admin_account_repository.py`](./repositories/admin_account_repository.py) | Đăng nhập bằng username/email, kiểm tra mật khẩu và cấp JWT admin. |
| Đăng nhập user | [`controllers/user_auth_controller.py`](./controllers/user_auth_controller.py) | [`services/user_auth_service.py`](./services/user_auth_service.py) | [`repositories/user_auth_repository.py`](./repositories/user_auth_repository.py) | Đăng ký, đăng nhập, xem/cập nhật hồ sơ và đổi mật khẩu. |
| Bảo vệ API | [`middlewares/admin_auth.py`](./middlewares/admin_auth.py), [`middlewares/user_auth.py`](./middlewares/user_auth.py) | — | Các repository tài khoản | Xác minh Bearer JWT, vai trò và trạng thái tài khoản hiện tại trong DB. |

Để thay đổi quyền truy cập một endpoint, kiểm tra `Depends(require_admin)` hoặc
`Depends(require_user)` trên router/endpoint của controller. ID người dùng cho
các thao tác cá nhân phải lấy từ claims của token, không lấy từ payload client.

### Quản lý nội dung cho admin

| Chức năng | Controller | Service | Repository |
| --- | --- | --- | --- |
| Địa điểm, danh mục và bản dịch tên | [`controllers/place_controller.py`](./controllers/place_controller.py), [`controllers/category_controller.py`](./controllers/category_controller.py) | [`services/place_service.py`](./services/place_service.py), [`services/category_service.py`](./services/category_service.py), [`services/localization_service.py`](./services/localization_service.py) | [`repositories/place_repository.py`](./repositories/place_repository.py), [`repositories/category_repository.py`](./repositories/category_repository.py), [`repositories/id_repository.py`](./repositories/id_repository.py) |
| Ảnh địa điểm | [`controllers/image_controller.py`](./controllers/image_controller.py) | [`services/image_service.py`](./services/image_service.py) | [`repositories/place_image_repository.py`](./repositories/place_image_repository.py) |
| Audio thuyết minh | [`controllers/audio_controller.py`](./controllers/audio_controller.py) | [`services/audio_service.py`](./services/audio_service.py), [`services/translation_service.py`](./services/translation_service.py) | [`repositories/place_audio_repository.py`](./repositories/place_audio_repository.py) |
| Văn bản thuyết minh | [`controllers/narration_controller.py`](./controllers/narration_controller.py) | [`services/narration_service.py`](./services/narration_service.py) | [`repositories/narration_repository.py`](./repositories/narration_repository.py) |
| Ngôn ngữ | [`controllers/language_controller.py`](./controllers/language_controller.py) | [`services/language_service.py`](./services/language_service.py) | [`repositories/language_repository.py`](./repositories/language_repository.py) |
| Bảng điều khiển/thống kê | [`controllers/dashboard_controller.py`](./controllers/dashboard_controller.py) | [`services/dashboard_service.py`](./services/dashboard_service.py) | [`repositories/dashboard_repository.py`](./repositories/dashboard_repository.py) |
| Nhật ký hoạt động admin | [`controllers/admin_activity_controller.py`](./controllers/admin_activity_controller.py) | [`services/admin_activity_service.py`](./services/admin_activity_service.py), [`services/admin_audit_service.py`](./services/admin_audit_service.py) | [`repositories/admin_activity_repository.py`](./repositories/admin_activity_repository.py) |
| Gợi ý dịch | [`controllers/translation_controller.py`](./controllers/translation_controller.py) | [`services/translation_service.py`](./services/translation_service.py) | — |

`AudioService` và `ImageService` quản lý cả metadata lẫn file; mỗi loại có thể
lưu trên đĩa hoặc trong MongoDB GridFS. Nếu thay đổi quy tắc upload/xóa/thay
file, đọc service tương ứng trước để giữ nhất quán hai nơi. `PlaceService` xử
lý slug, kiểm tra danh mục và tạo thư mục ảnh khi tạo địa điểm.

Dashboard lọc lượt truy cập website theo ngày và tính một lượt cho mỗi phiên
tab; các lần tải lại trong cùng tab không cộng thêm, còn phiên/tab mới được tính
lượt mới. Danh sách online gồm tài khoản đã đăng nhập và số phiên khách chưa
đăng nhập; trạng thái được xác định theo hoạt động trong khoảng thời gian cấu
hình. Thống kê lượt nghe theo địa điểm và ngôn ngữ lấy từ lịch sử nghe của tài
khoản và ghi nhận riêng các lượt nghe khách ẩn danh qua
`POST /api/user/listening-usage`; dữ liệu này không gắn với tài khoản cá nhân.

#### Chuyển văn bản thành giọng nói (Text-to-Speech)

Luồng tạo audio thuyết minh bằng TTS bắt đầu từ API admin
`POST /api/admin/places/{place_id}/audios` trong
[`controllers/audio_controller.py`](./controllers/audio_controller.py). API
chuyển dữ liệu yêu cầu cho `AudioService.generate()` trong
[`services/audio_service.py`](./services/audio_service.py). Service chọn văn
bản đã dịch (nếu có) hoặc văn bản nguồn, rồi gọi `_generate_tts_audio()`;
hàm này dùng thư viện `edge-tts` để tạo file MP3 với giọng đọc tương ứng ngôn
ngữ. Sau khi tạo file, service tính thời lượng, lưu file bằng backend được cấu
hình rồi ghi metadata vào MongoDB. Mặc định `AUDIO_STORAGE_BACKEND=local` lưu
file dưới `/uploads/audio/`; đặt `AUDIO_STORAGE_BACKEND=gridfs` để lưu file mới
trong MongoDB GridFS và phát qua endpoint `/api/audio/files/{file_id}`.
`AUDIO_GRIDFS_BUCKET` tùy chọn tên bucket, mặc định là `audio`. File local cũ
không tự được chuyển sang GridFS. Ảnh dùng cấu hình độc lập:
`IMAGE_STORAGE_BACKEND=gridfs` để lưu ảnh mới trong bucket mặc định `images`
và phát qua `/api/images/files/{file_id}`; đổi tên bucket bằng
`IMAGE_GRIDFS_BUCKET`. Ảnh local cũ cũng không tự được chuyển.

Các giọng mặc định theo ngôn ngữ được khai báo trong `VOICES` của
`audio_service.py`. Nếu cần thay đổi cách chọn văn bản, giọng đọc hoặc xử lý
lỗi từ dịch vụ TTS, hãy bắt đầu từ `AudioService.generate()` và
`_generate_tts_audio()`. Giao diện quản trị gửi yêu cầu này tại
[`AudioManagement.jsx`](../../frontend/src/pages/AudioManagement.jsx).

### Tài khoản và hoạt động user

| Chức năng | Controller | Service | Repository |
| --- | --- | --- | --- |
| Admin quản lý tài khoản user | [`controllers/user_account_controller.py`](./controllers/user_account_controller.py) | [`services/user_account_service.py`](./services/user_account_service.py) | [`repositories/user_account_repository.py`](./repositories/user_account_repository.py) |
| Trải nghiệm địa điểm, địa điểm đã lưu, lịch sử nghe, phiên truy cập và sự kiện sử dụng | [`controllers/user_activity_controller.py`](./controllers/user_activity_controller.py) | [`services/user_activity_service.py`](./services/user_activity_service.py), [`services/place_service.py`](./services/place_service.py) | [`repositories/user_activity_repository.py`](./repositories/user_activity_repository.py), cùng các repository địa điểm/danh mục |

`UserActivityService` kiểm tra quy tắc nghiệp vụ; `UserActivityRepository` thực
hiện truy vấn và ghi dữ liệu liên quan đến nhiều collection. Khi sửa dữ liệu
hoạt động, chú ý điều kiện sở hữu: bản ghi phải thuộc `UserId` của token hoặc
phiên phải thuộc user đó.

## Router và nơi tìm endpoint

Các file trong [`routes/`](./routes/) thường chỉ export router từ controller
cùng tên. Tiền tố URL và endpoint được khai báo tại controller:

- Admin: `auth`, `places`, `categories`, `images`, `audios`, `narrations`,
  `languages`, `users`, `activity-logs`, `dashboard`, `translations`.
- User: `auth`, `places`, `saved-places`, `listening-history`, `sessions`,
  `usage-events`.

Muốn biết chính xác method, URL, payload và response, mở controller tương ứng
và tìm decorator `@router.get`, `@router.post`, `@router.patch`, `@router.put`
hoặc `@router.delete`. Pydantic model đặt gần đầu controller là hợp đồng dữ
liệu đầu vào/đầu ra; ràng buộc của trường thường được khai báo bằng `Field` và
validator.

## Cách lần theo hoặc thay đổi một chức năng

1. Tìm URL/decorator trong controller liên quan.
2. Xem model request/response và dependency xác thực để hiểu dữ liệu đầu vào,
   đầu ra và quyền truy cập.
3. Theo lời gọi từ controller sang service để tìm quy tắc nghiệp vụ, kiểm tra
   dữ liệu và xử lý lỗi.
4. Theo service sang repository để sửa truy vấn MongoDB hoặc tên trường/collection.
5. Nếu chức năng dùng cấu hình, kiểm tra `Settings` và `get_settings()`; nếu
   chức năng nhận/trả file, kiểm tra cả service lưu file và mount static trong
   `main.py`.
6. Chạy test tương ứng trong [`../tests/`](../tests/). Có thể chạy toàn bộ
   backend tests từ thư mục `backend` bằng
   `python -m unittest discover -s tests -v`.

Ví dụ: để đổi quy tắc hiển thị địa điểm cho người dùng, lần theo
`user_activity_controller.py` -> `UserActivityService` -> các hàm truy vấn
địa điểm trong `UserActivityRepository`. Để đổi thông tin trả về ở API admin,
bắt đầu từ controller và response model rồi lần tiếp xuống service/repository
nếu dữ liệu hoặc quy tắc nghiệp vụ cũng cần đổi.
