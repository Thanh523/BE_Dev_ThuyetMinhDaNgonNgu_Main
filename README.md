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
Creating a place also creates an image folder under `backend/uploads/images`
named `<PlaceId>-<slug>`; uploaded images for that place are stored there.
Audio management uses the `PlaceAudios` collection, linked by `PlaceId` and
`Language`. Uploaded audio files are validated with `mutagen` and limited to
50 MB by default. Files are stored under
`backend/uploads/audio/<PlaceId>-<slug>` by default. The admin audio page
provides audio upload and management without a text-to-speech form.

Backend management code follows routes → controllers → services → repositories.
Route modules aggregate and register endpoint routers; controllers handle HTTP
and response models; services enforce validation and business rules; and
repositories own MongoDB operations. Admin authentication and activity logging
use the same service/repository split. The shared integer-ID allocator is in
`src/repositories/id_repository.py`.

### Run locally

Put Atlas settings in `backend/atlas-credentials.env` (or the existing
`backend/src/atlas_credential.env`; both files are ignored by Git), or set
them in the shell. For example:

```powershell
MONGODB_URI=mongodb+srv://<database-user>:<url-encoded-password>@<cluster-host>/?retryWrites=true&w=majority
MONGODB_DATABASE=SaigonEcho
JWT_KEY=<random-secret-at-least-32-characters>
```

Generate a secret locally with
`python -c "import secrets; print(secrets.token_urlsafe(48))"` and put the
result in `JWT_KEY`; do not share or commit it. The built-in admin login signs
JWTs using `JWT_ALGORITHM` (HS256 by default) that expire after 8 hours. For
HS256, the secret must be at least 32 bytes. User registration and login use
the same JWT key but issue user-role tokens distinct from admin tokens.
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
The **Hình ảnh** section automatically loads the image library for all places;
choose a place by name only when uploading an image.

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
| `GET` | `/api/admin/images` | List all images with their place names |
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
| `PATCH` | `/api/admin/users/{user_id}` | Update a user's name and email |
| `PATCH` | `/api/admin/users/{user_id}/status` | Activate or deactivate a user account |
| `DELETE` | `/api/admin/users/{user_id}` | Soft-delete a user when no related records exist |
| `GET` | `/api/admin/users/{user_id}/activity` | View saved places, listening history, visitor sessions, and usage events |
| `POST` | `/api/user/auth/register` | Register a user account (email is not verified by email) |
| `POST` | `/api/user/auth/login` | Sign in with email/password and receive a user JWT |
| `GET` | `/api/user/auth/me` | Get the authenticated user's profile |
| `GET` | `/api/user/places` | Search and page through visible places |
| `GET` | `/api/user/saved-places` | Page through the authenticated user's saved places |
| `POST` | `/api/user/saved-places/{place_id}` | Save a visible place |
| `DELETE` | `/api/user/saved-places/{place_id}` | Remove a saved place |
| `GET` | `/api/user/listening-history` | Page through the authenticated user's listening history |
| `POST` | `/api/user/listening-history` | Record a completed or partial audio play |
| `POST` | `/api/user/sessions` | Start a visitor session |
| `GET` | `/api/user/sessions` | Page through the authenticated user's sessions |
| `PATCH` | `/api/user/sessions/{session_id}` | Update session activity or end the session |
| `POST` | `/api/user/usage-events` | Record an idempotent usage event for an owned session |
| `GET` | `/api/user/usage-events` | Page through events from the authenticated user's sessions |
| `GET` | `/api/admin/places/{place_id}/audios` | List a place's audio by language |
| `POST` | `/api/admin/places/{place_id}/audios` | Translate text and generate an MP3 narration |
| `POST` | `/api/admin/places/{place_id}/audios/upload` | Upload an audio file with multipart fields `file`, `language`, and optional title/voice |
| `PUT` | `/api/admin/audios/{audio_id}/file` | Replace an audio file |
| `PATCH` | `/api/admin/audios/{audio_id}` | Update title, language, voice name, or active status |
| `DELETE` | `/api/admin/audios/{audio_id}` | Delete audio metadata and its stored file |

The user list accepts optional `search` (name/email), `is_active`, `skip`, and
`limit` query parameters. Admin user-management endpoints require an admin token;
profile, status, and delete operations are recorded in `AdminActivityLogs`.
Self-service registration creates an active account immediately; no email
verification or password-reset email is implemented. Passwords must be 12-128
characters and are stored only as an Argon2 hash. User login requires a
configured `JWT_KEY` (at least 32 bytes for HS256) and returns an 8-hour JWT.
User tokens are distinct from admin tokens; authenticated user endpoints derive
`UserId` from the token and reject inactive or soft-deleted accounts.
User deletion is rejected while records exist in `SavedPlaces`,
`ListeningHistory`, or `VisitorSessions`, or while `UsageEvents` reference one
of the user's visitor sessions. Deletion is soft: the account is marked with
`IsDeleted` and `DeletedAt`, deactivated, and hidden from the user list; its
record and related history remain in MongoDB. This retains the account
reference if activity is written concurrently with deletion. Deleted users'
email addresses remain reserved by the unique index. User email addresses are
unique without case sensitivity. The activity endpoint accepts an optional
`limit` (1-50, default 20) and reads from `SavedPlaces`, `ListeningHistory`,
`VisitorSessions`, and `UsageEvents`. User activity endpoints are scoped to
the authenticated account. Saved places can reference visible places only;
listening history accepts active audio IDs. Each listening-history submission
creates a new record. User sessions use `LastSeenAt` as in the ERD. A
`ClientEventId` is unique and retries with the same event payload are
idempotent; reusing it for different event data returns `409`.

Uploads accept valid JPEG, PNG, and WebP files up to 10 MB each. If captions or
sort orders are provided during a batch upload, provide one value per file.
When sort orders are omitted, new images are appended after the current highest
order. Image URLs are served under `/uploads/images/`.
Audio uploads accept MP3, WAV, OGG, M4A, and FLAC up to 50 MB by default.
The backend validates the file contents and stores the detected duration.
Adjust the limit with `MAX_AUDIO_SIZE_BYTES`; audio URLs are served under
`/uploads/audio/`.

Run the backend unit tests from `backend` with
`python -m unittest discover -s tests -v`.

Set `MONGODB_PLACES_COLLECTION`, `MONGODB_PLACE_IMAGES_COLLECTION`,
`MONGODB_AUDIO_COLLECTION`, `AUDIO_STORAGE_DIR`,
`MONGODB_ADMIN_ACCOUNTS_COLLECTION`,
`MONGODB_ADMIN_ACTIVITY_LOGS_COLLECTION`, `MONGODB_USER_ACCOUNTS_COLLECTION`,
`MONGODB_SAVED_PLACES_COLLECTION`, `MONGODB_LISTENING_HISTORY_COLLECTION`,
`MONGODB_VISITOR_SESSIONS_COLLECTION`, `MONGODB_USAGE_EVENTS_COLLECTION`,
`MONGODB_NARRATIONS_COLLECTION`,
`MONGODB_CATEGORIES_COLLECTION`,
`MONGODB_COUNTERS_COLLECTION`, `IMAGE_STORAGE_DIR`, and `CORS_ORIGINS` to
override the defaults. The MongoDB database and collection names and file
storage path are configurable for integration with the existing application.