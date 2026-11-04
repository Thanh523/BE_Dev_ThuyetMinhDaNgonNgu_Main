# BE_Dev_ThuyetMinhDaNgonNgu_Main

## Backend image management API

The backend is a FastAPI application using MongoDB. It expects a `Places`
collection with a `PlaceId` field, and stores image metadata in `PlaceImages`
with `ImageId`, `PlaceId`, `FileUrl`, `SortOrder`, and `Caption` fields.
Image files are stored under `backend/uploads/images` by default.

The admin UI also manages places and categories. `Places` uses `PlaceId`,
`CategoryId`, `PlaceName`, `Slug`, `Address`, and `IsVisible`; numeric IDs are
allocated through the `Counters` collection. `Categories` uses `CategoryId`,
`CategoryName`, and `Description`. Place slugs are generated from the name
when omitted and must be unique. Deleting a place with related `PlaceImages`,
or a category referenced by places, is rejected rather than cascading.

Backend management code follows routes → controllers → services → repositories.
Route modules aggregate and register endpoint routers; controllers handle HTTP
and response models; services enforce validation and business rules; and
repositories own MongoDB operations. Admin authentication and activity logging
use the same service/repository split. The shared integer-ID allocator is in
`src/repositories/id_repository.py`.

### Run locally

Put Atlas settings in `backend/atlas-credentials.env` (this file is ignored by
Git), or set them in the shell. For example:

```powershell
MONGODB_URI=mongodb+srv://<database-user>:<url-encoded-password>@<cluster-host>/?retryWrites=true&w=majority
MONGODB_DATABASE=SaigonEcho
JWT_KEY=<random-secret-at-least-32-characters>
```

Generate a secret locally with
`python -c "import secrets; print(secrets.token_urlsafe(48))"` and put the
result in `JWT_KEY`; do not share or commit it. The built-in admin login signs
JWTs using `JWT_ALGORITHM` (HS256 by default) that expire after 8 hours. For
HS256, the secret must be at least 32 bytes. No public registration is provided.
The application loads `atlas-credentials.env` automatically; existing process
environment variables take precedence. From the `backend` directory, install
dependencies, create the first admin, and start the API:

```powershell
python -m pip install -r requirements.txt
python -m src.create_admin
python -m uvicorn src.main:app --reload
```

The admin command prompts for a username, email, and password (minimum 12
characters); it stores the account in `AdminAccounts` using the fields shown in
the schema, and stores only an Argon2 password hash. Successful logins and
image changes are recorded in `AdminActivityLogs`. Admin passwords must not be
sent over an untrusted connection; use HTTPS and configure login rate limiting
before deploying beyond local development.

The current Atlas database did not contain `Places` or `Categories` when this
feature was added. Start the API, sign in, create one or more categories in the
**Quản lý danh mục** section, then add places and choose a category.

`AdminAccounts` stores `AdminId`, `Username`, `Email`, `PasswordHash`, `Role`,
`IsActive`, `CreatedAt`, `UpdatedAt`, and `LastLoginAt`. `AdminActivityLogs`
stores `LogId`, `AdminId`, `Action`, `EntityName`, `EntityId`, `Description`,
and `CreatedAt`.

Login at `POST /api/admin/auth/login` with JSON fields `username` (username or
email) and `password`. The returned bearer token authorizes the
image-management APIs.
The `GET /api/admin/activity-logs` endpoint returns the latest admin activity
records (up to 200 per request). Inactive accounts cannot log in, and existing
tokens are rejected after an account is deactivated.

Never commit `atlas-credentials.env`, `JWT_KEY`, or other secrets.

### Endpoints

All management endpoints require `Authorization: Bearer <admin-jwt>`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/admin/places/{place_id}/images` | List a place's images by `sort_order` |
| `POST` | `/api/admin/places/{place_id}/images` | Upload multiple images as multipart field `files`; optional repeated `captions` and `sort_orders` fields |
| `PATCH` | `/api/admin/images/{image_id}` | Update `caption`, `sort_order`, or both |
| `DELETE` | `/api/admin/images/{image_id}` | Permanently delete image metadata and file |
| `GET` | `/api/admin/places` | Search/filter and page places |
| `GET` | `/api/admin/places/{place_id}` | View place details |
| `POST` | `/api/admin/places` | Create a place |
| `PATCH` | `/api/admin/places/{place_id}` | Update place fields |
| `PATCH` | `/api/admin/places/{place_id}/visibility` | Hide/show a place |
| `DELETE` | `/api/admin/places/{place_id}` | Delete a place when no images reference it |
| `GET` | `/api/admin/categories` | List categories |
| `POST` | `/api/admin/categories` | Create a category |
| `PATCH` | `/api/admin/categories/{category_id}` | Update a category name and description |
| `DELETE` | `/api/admin/categories/{category_id}` | Delete an unused category |
| `GET` | `/api/admin/users` | Search and page user accounts (never returns password hashes) |
| `PATCH` | `/api/admin/users/{user_id}/status` | Activate or deactivate a user account |

The user list accepts optional `search` (name/email), `is_active`, `skip`, and
`limit` query parameters. User management endpoints require an admin token;
status changes are recorded in `AdminActivityLogs`.

Uploads accept valid JPEG, PNG, and WebP files up to 10 MB each. If captions or
sort orders are provided during a batch upload, provide one value per file.
When sort orders are omitted, new images are appended after the current highest
order. Image URLs are served under `/uploads/images/`.

Run the backend unit tests from `backend` with
`python -m unittest discover -s tests -v`.

Set `MONGODB_PLACES_COLLECTION`, `MONGODB_PLACE_IMAGES_COLLECTION`,
`MONGODB_ADMIN_ACCOUNTS_COLLECTION`,
`MONGODB_ADMIN_ACTIVITY_LOGS_COLLECTION`, `MONGODB_USER_ACCOUNTS_COLLECTION`,
`MONGODB_CATEGORIES_COLLECTION`,
`MONGODB_COUNTERS_COLLECTION`, `IMAGE_STORAGE_DIR`, and `CORS_ORIGINS` to
override the defaults. The MongoDB database and collection names and file
storage path are configurable for integration with the existing application.