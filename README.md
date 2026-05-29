# MVA Project — YouTube-Clone (Microservices)

A full-stack YouTube-like video platform built with a microservices architecture. Users can register, upload videos, and watch them after automatic transcoding.

---

## Architecture Overview

```
Browser (React + Vite)
        │
        ▼
   Nginx (port 80)  ← single entry point / reverse proxy
   /api/auth   →  Auth Service      (FastAPI, port 8001)
   /api/upload →  Upload Service    (FastAPI, port 8002)
   /api/catalog→  Catalog Service   (FastAPI, port 8003)
                                          │
                              Redis Queue (video_transcode_queue)
                                          │
                                          ▼
                                  Transcoder Worker  (Python, background)
                                          │
                              MinIO Object Storage (ports 9000/9001)
                                          │
                              PostgreSQL (auth DB + catalog DB, port 5433)
```

### Services

| Service | Tech | Responsibility |
|---|---|---|
| **auth** | FastAPI + SQLAlchemy + JWT | Register, login, profile, subscriptions |
| **upload** | FastAPI + boto3 + Redis | Validate, store raw video in MinIO, enqueue transcode job |
| **transcoder** | Python worker + FFmpeg + boto3 | Consume Redis queue, transcode with FFmpeg, upload to MinIO, update DB |
| **catalog** | FastAPI + SQLAlchemy | List/get videos, comments, likes |
| **frontend** | React 19 + Vite + Tailwind CSS | SPA — home feed, auth, profile |
| **nginx** | Nginx | Reverse proxy routing all `/api/*` traffic |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- [Node.js 18+](https://nodejs.org/) (for frontend dev only)

---

## Quick Start

### 1. Start all backend services

```bash
cd infrastructure
docker compose up --build
```

This starts: PostgreSQL, Redis, MinIO, Auth, Upload, Catalog, Transcoder, and Nginx.

| Service | URL |
|---|---|
| Nginx gateway | http://localhost |
| Auth API docs | http://localhost/api/auth/docs |
| Upload API docs | http://localhost/api/upload/docs |
| Catalog API docs | http://localhost/api/catalog/docs |
| MinIO Console | http://localhost:9001 (user: `minioadmin`, pass: `minioadmin`) |

### 2. Start the frontend (dev mode)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 and proxies API calls through Nginx on port 80.

---

## API Reference

All routes are accessed through the Nginx gateway at `http://localhost`.

### Auth Service — `/api/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | No | Register a new user |
| `POST` | `/api/auth/login` | No | Login, returns JWT |
| `GET` | `/api/auth/verify` | Bearer | Validate token, return user info |
| `PATCH` | `/api/auth/profile` | Bearer | Update username / bio / password |
| `PUT` | `/api/auth/update-profile` | Bearer | Full profile update |
| `POST` | `/api/auth/subscribe/{user_id}` | Bearer | Subscribe to a user |
| `GET` | `/api/auth/subscriptions` | Bearer | List subscriptions |

**Register**
```json
POST /api/auth/register
{ "username": "alice", "email": "alice@example.com", "password": "secret" }
```

**Login**
```
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded
username=alice&password=secret
```
Returns: `{ "access_token": "<jwt>", "token_type": "bearer" }`

---

### Upload Service — `/api/upload`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/upload/` | Bearer | Upload a video file |
| `GET` | `/api/upload/health` | No | Health check |

**Upload a video** (multipart form)
```
POST /api/upload/
Authorization: Bearer <token>
Content-Type: multipart/form-data

title=My Video
description=Optional description
video=<file.mp4>
```

- Accepted types: `video/mp4`, `video/x-matroska`, `video/quicktime`
- Max file size: **100 MB**
- Returns video metadata and queues a transcode job

---

### Catalog Service — `/api/catalog`

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/catalog/videos` | No | List latest 10 videos (supports `?search=` and `?uploader_id=`) |
| `GET` | `/api/catalog/videos/{id}` | No | Get a single video |
| `POST` | `/api/catalog/videos` | No | Create video entry (internal use) |
| `DELETE` | `/api/catalog/videos/{id}` | No | Delete a video |
| `GET` | `/api/catalog/videos/{id}/comments` | No | List comments |
| `POST` | `/api/catalog/videos/{id}/comments` | No | Post a comment |
| `POST` | `/api/catalog/videos/{id}/like` | No | Toggle like |
| `GET` | `/api/catalog/health` | No | Health check |

---

## Video Pipeline

```
User uploads video
      │
      ▼
Upload Service → stores raw file in MinIO (raw-videos bucket)
      │
      ▼
Creates DB record (status: PENDING) + pushes job to Redis queue
      │
      ▼
Transcoder Worker picks job from Redis
      │
      ├─ Downloads raw file from MinIO
      ├─ Transcodes to H.264/AAC MP4 via FFmpeg
      ├─ Extracts thumbnail (at 2s, fallback 0s)
      ├─ Uploads processed.mp4 + thumbnail.jpg to MinIO (processed-videos bucket)
      └─ Updates DB record (status: READY, sets processed_path + thumbnail_path)
```

Video statuses: `PENDING` → `READY` or `FAILED`

---

## Database Schema

Two PostgreSQL databases are created automatically on first run.

**`auth` database**
- `users` — id, username, email, password_hash, bio, created_at
- `subscriptions` — follower_id, leader_id

**`catalog` database**
- `videos` — id, uploader_id, title, description, thumbnail_path, raw_file_path, processed_path, status, created_at
- `comments` — id, video_id, user_id, content, created_at
- `likes` — id, video_id, user_id, created_at (unique per user+video)

---

## Environment Variables

Key variables (set in `docker-compose.yml`; override as needed):

| Variable | Default | Used by |
|---|---|---|
| `SECRET_KEY` | `supersecret` | auth, upload |
| `DB_HOST` | `postgres` | auth, catalog |
| `DATABASE_URL` | `postgresql://...` | upload, transcoder |
| `REDIS_URL` | `redis://redis:6379/0` | upload, transcoder |
| `MINIO_ENDPOINT` | `http://minio:9000` | upload, transcoder |
| `MINIO_ACCESS_KEY` | `minioadmin` | upload, transcoder |
| `MINIO_SECRET_KEY` | `minioadmin` | upload, transcoder |
| `AUTH_SERVICE_URL` | `http://auth:8001` | upload |

---

## Running the E2E Smoke Test

Place a `sample.mp4` in the `tests/` directory, then:

```bash
cd tests
python test_pipeline.py
```

The test will:
1. Register + login a test user
2. Upload `sample.mp4`
3. Print the upload service response

Override credentials via env vars: `E2E_USERNAME`, `E2E_PASSWORD`, `E2E_EMAIL`.

---

## Frontend Structure

```
frontend/src/
├── components/
│   ├── Auth/         # LoginView, RegisterView
│   ├── Home/         # HomeFeedView (video grid + player modal)
│   └── Layout/       # TopNavbar, LeftSidebar
├── utils/auth.js     # localStorage token helpers
└── App.jsx           # Root — routing, auth state, session hydration
```

The frontend is a single-page app with client-side routing via a `page` state variable. JWT is stored in `localStorage`.

---

## Project Structure

```
mva_project/
├── frontend/           # React + Vite SPA
├── infrastructure/
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── initdb/init.sql # DB schema bootstrap
├── services/
│   ├── auth/           # FastAPI auth service
│   ├── catalog/        # FastAPI catalog service
│   ├── upload/         # FastAPI upload service
│   └── transcoder/     # Python worker (FFmpeg)
└── tests/
    └── test_pipeline.py # E2E smoke test
```
