# Saigon Echo image demo

This small React page exercises the backend image-management API.

## Run

From `frontend`:

```powershell
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). Start the backend from
`backend` with `python -m uvicorn src.main:app --reload`.
The backend allows both `localhost:5173` and `127.0.0.1:5173` by default; restart
the backend after changing `CORS_ORIGINS`.

The **Demo người dùng** tab works without an admin login. Enter the backend
URL, register a user, then sign in to try saved places, listening history,
visitor sessions, and usage events. The user token stays in page memory and is
not stored in browser storage. Use IDs that already exist in MongoDB for
`PlaceId`, `AudioId`, and optional `NarrationId`; the backend rejects missing or
inactive content references.

For admin management, enter the backend URL and admin username/password. A `PlaceId` that exists in
the `Places` collection is optional during login. The login endpoint returns an
admin JWT valid for 8 hours. The token stays in page memory and is not saved to
browser storage.


After login, use the separate **Địa điểm**, **Hình ảnh**, **Danh mục**, and
**Người dùng** pages. The user page searches accounts by name/email, filters
by active status, pages through results, and lets an admin lock or unlock an
account, edit the user's name and email, and view saved places, listening
history, visitor sessions, and usage events when available. The admin page
manages existing user accounts. Admins can soft-delete a user only if no
related activity records remain. This
disables the account and hides it from the list while retaining the account
record and activity history in MongoDB. The places page
supports place
CRUD, detail view, search, filters, visibility toggling, and safe deletion
checks. The categories page supports category CRUD. The images page can list a
place's images, upload JPEG/PNG/WebP files (up to 10 MB each), update captions
and sort order, and delete images.
Leaving all sort orders blank lets the backend append uploaded images
automatically. The backend CORS configuration must include the frontend's
origin if it has been changed from its defaults. See the repository README for
creating the first admin account and configuring the JWT signing key.
