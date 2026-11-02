# BE_Dev_ThuyetMinhDaNgonNgu_Main

## Backend image management API

The backend is a FastAPI application using MongoDB. It expects a `Places`
collection with a `PlaceId` field, and stores image metadata in `PlaceImages`
with `ImageId`, `PlaceId`, `FileUrl`, `SortOrder`, and `Caption` fields.
Image files are stored under `backend/uploads/images` by default.

### Run locally

Put Atlas settings in `backend/atlas-credentials.env` (this file is ignored by
Git), or set them in the shell. For example:

```powershell
MONGODB_URI=mongodb+srv://<database-user>:<url-encoded-password>@<cluster-host>/?retryWrites=true&w=majority
MONGODB_DATABASE=multilingual_guide
JWT_KEY=<key-matching-the-admin-token-issuer>
```

The application loads `atlas-credentials.env` automatically; existing process
environment variables take precedence. From the `backend` directory, install
dependencies and start the API:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn src.main:app --reload
```

The JWT issuer must include a future `exp` claim and a string claim `role` with
value `admin`. Configure `JWT_ALGORITHM`, `JWT_ROLE_CLAIM`, `JWT_ISSUER`, and
`JWT_AUDIENCE` to match the issuer. For HS256, use a strong key of at least 32
bytes; for asymmetric algorithms, `JWT_KEY` must contain the verification key.
Never commit `atlas-credentials.env`, `JWT_KEY`, or other secrets.

### Endpoints

All management endpoints require `Authorization: Bearer <admin-jwt>`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/admin/places/{place_id}/images` | List a place's images by `sort_order` |
| `POST` | `/api/admin/places/{place_id}/images` | Upload multiple images as multipart field `files`; optional repeated `captions` and `sort_orders` fields |
| `PATCH` | `/api/admin/images/{image_id}` | Update `caption`, `sort_order`, or both |
| `DELETE` | `/api/admin/images/{image_id}` | Permanently delete image metadata and file |

Uploads accept valid JPEG, PNG, and WebP files up to 10 MB each. If captions or
sort orders are provided during a batch upload, provide one value per file.
When sort orders are omitted, new images are appended after the current highest
order. Image URLs are served under `/uploads/images/`.

Run the backend unit tests from `backend` with
`python -m unittest discover -s tests -v`.

Set `MONGODB_PLACES_COLLECTION`, `MONGODB_PLACE_IMAGES_COLLECTION`,
`IMAGE_STORAGE_DIR`, and `CORS_ORIGINS` to override the defaults. The MongoDB
database and collection names, JWT claim, algorithm, and file storage path are
configurable for integration with the existing application.