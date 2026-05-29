import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import boto3
import redis
import requests
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from redis.exceptions import RedisError
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB limit
ALLOWED_CONTENT_TYPES = ["video/mp4", "video/x-matroska", "video/quicktime"]
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth:8001")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
TRANSCODE_QUEUE = os.environ.get("TRANSCODE_QUEUE", "video_transcode_queue")
_minio_endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ENDPOINT = (
    _minio_endpoint
    if _minio_endpoint.startswith(("http://", "https://"))
    else f"http://{_minio_endpoint}"
)
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
RAW_VIDEOS_BUCKET = os.environ.get("RAW_VIDEOS_BUCKET", "raw-videos")
AUTH_REQUEST_TIMEOUT = float(os.environ.get("AUTH_REQUEST_TIMEOUT", "5"))

DB_URL = os.environ.get("DATABASE_URL") or (
    f"postgresql://{os.environ.get('DB_USER', 'postgres')}:"
    f"{os.environ.get('DB_PASSWORD', 'postgres')}@"
    f"{os.environ.get('DB_HOST', 'postgres')}:"
    f"{os.environ.get('DB_PORT', '5432')}/"
    f"{os.environ.get('DB_NAME', 'catalog')}"
)

# ---------------------------------------------------------------------------
# Database (catalog.videos)
# ---------------------------------------------------------------------------

engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    uploader_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_path = Column(String(512), nullable=True)
    raw_file_path = Column(String(512), nullable=True)
    processed_path = Column(String(512), nullable=True)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# External clients
# ---------------------------------------------------------------------------


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=os.environ.get("MINIO_REGION", "us-east-1"),
    )


def get_redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def ensure_raw_videos_bucket(s3_client) -> None:
    try:
        s3_client.head_bucket(Bucket=RAW_VIDEOS_BUCKET)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code not in ("404", "NoSuchBucket", "NotFound"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MinIO bucket check failed: {error_code}",
            ) from exc
        try:
            s3_client.create_bucket(Bucket=RAW_VIDEOS_BUCKET)
            logger.info("Created MinIO bucket: %s", RAW_VIDEOS_BUCKET)
        except (BotoCoreError, ClientError) as create_exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to initialize MinIO bucket",
            ) from create_exc


def extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
        )
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


def verify_token_with_auth_service(token: str) -> dict:
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/verify",
            headers={"Authorization": f"Bearer {token}"},
            timeout=AUTH_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.exception("Auth service unreachable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable",
        ) from exc

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from auth service",
        ) from exc


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    token = extract_bearer_token(authorization)
    return verify_token_with_auth_service(token)


def upload_video_to_minio(s3_client, file: UploadFile, object_key: str) -> str:
    ensure_raw_videos_bucket(s3_client)
    extra_args = {}
    if file.content_type:
        extra_args["ContentType"] = file.content_type

    try:
        if hasattr(file.file, "seek"):
            file.file.seek(0)
        if extra_args:
            s3_client.upload_fileobj(file.file, RAW_VIDEOS_BUCKET, object_key, ExtraArgs=extra_args)
        else:
            s3_client.upload_fileobj(file.file, RAW_VIDEOS_BUCKET, object_key)
    except (BotoCoreError, ClientError) as exc:
        logger.exception("MinIO upload failed for key %s", object_key)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to upload video to storage",
        ) from exc

    return f"{RAW_VIDEOS_BUCKET}/{object_key}"


def delete_minio_object(s3_client, object_key: str) -> None:
    try:
        s3_client.delete_object(Bucket=RAW_VIDEOS_BUCKET, Key=object_key)
    except (BotoCoreError, ClientError):
        logger.exception("Failed to clean up MinIO object %s", object_key)


def enqueue_transcode_job(redis_client: redis.Redis, video_id: int, raw_file_path: str) -> None:
    payload = json.dumps({"video_id": video_id, "raw_file_path": raw_file_path})
    try:
        redis_client.lpush(TRANSCODE_QUEUE, payload)
    except RedisError as exc:
        logger.exception("Redis enqueue failed for video_id=%s", video_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to queue video for processing",
        ) from exc


def guess_extension(filename: Optional[str]) -> str:
    if not filename:
        return ".mp4"
    suffix = Path(filename).suffix.lower()
    if suffix and len(suffix) <= 10:
        return suffix
    return ".mp4"


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    video_id: int
    uploader_id: int
    title: str
    raw_file_path: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Upload Service",
    root_path="/api/upload",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "upload"}


@app.post("/", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_video(
    title: str = Form(...),
    description: str = Form(""),
    video: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if video.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Unsupported file type: {video.content_type}. Allowed: {ALLOWED_CONTENT_TYPES}"
        )
    video.file.seek(0, 2)
    file_size = video.file.tell()
    video.file.seek(0)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="File size exceeds the 100MB limit."
        )

    if not video.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video file is required",
        )

    uploader_id = current_user.get("id")
    if not uploader_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id missing",
        )

    object_key = f"{uuid.uuid4()}{guess_extension(video.filename)}"
    s3_client = get_s3_client()
    raw_file_path: Optional[str] = None
    video_id: Optional[int] = None

    try:
        raw_file_path = upload_video_to_minio(s3_client, video, object_key)

        try:
            db_video = Video(
                uploader_id=uploader_id,
                title=title.strip(),
                description=description.strip() or None,
                raw_file_path=raw_file_path,
                status="PENDING",
            )
            db.add(db_video)
            db.commit()
            db.refresh(db_video)
            video_id = db_video.id
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database insert failed")
            delete_minio_object(s3_client, object_key)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to save video metadata",
            ) from exc

        redis_client = get_redis_client()
        try:
            enqueue_transcode_job(redis_client, video_id, raw_file_path)
        except HTTPException:
            db.delete(db_video)
            db.commit()
            delete_minio_object(s3_client, object_key)
            raise

        return UploadResponse(
            video_id=video_id,
            uploader_id=uploader_id,
            title=db_video.title,
            raw_file_path=raw_file_path,
            status=db_video.status,
            message="Video uploaded and queued for processing",
        )
    finally:
        video.file.close()
