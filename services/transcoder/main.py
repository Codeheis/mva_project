import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Tuple

import boto3
import redis
from botocore.exceptions import BotoCoreError, ClientError
from redis.exceptions import RedisError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("transcoder")


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
PROCESSED_VIDEOS_BUCKET = os.environ.get("PROCESSED_VIDEOS_BUCKET", "processed-videos")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/catalog"
)


def get_redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=os.environ.get("MINIO_REGION", "us-east-1"),
    )


def ensure_bucket_exists(s3_client, bucket_name: str) -> None:
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchBucket", "NotFound"):
            logger.info("Creating bucket '%s'", bucket_name)
            s3_client.create_bucket(Bucket=bucket_name)
            return
        raise


def parse_bucket_and_key(raw_file_path: str) -> Tuple[str, str]:
    path = raw_file_path.strip().lstrip("/")
    if "/" not in path:
        raise ValueError("raw_file_path must be in '<bucket>/<key>' format")
    return path.split("/", 1)


def run_transcode_ffmpeg(input_file: Path, output_file: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_file),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_file),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def run_thumbnail_ffmpeg(input_file: Path, thumbnail_file: Path) -> None:
    primary_cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        "00:00:02",
        "-i",
        str(input_file),
        "-vframes",
        "1",
        str(thumbnail_file),
    ]
    fallback_cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        "00:00:00",
        "-i",
        str(input_file),
        "-vframes",
        "1",
        str(thumbnail_file),
    ]

    try:
        subprocess.run(primary_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        logger.warning("Thumbnail at 2s failed; retrying at 0s")
        subprocess.run(fallback_cmd, check=True, capture_output=True, text=True)


def set_video_ready(
    engine,
    video_id: int,
    processed_path: str,
    thumbnail_path: str,
) -> None:
    query = text(
        """
        UPDATE videos
        SET processed_path = :processed_path,
            thumbnail_path = :thumbnail_path,
            status = 'READY'
        WHERE id = :video_id AND status = 'PENDING'
        """
    )
    with engine.begin() as connection:
        result = connection.execute(
            query,
            {
                "video_id": video_id,
                "processed_path": processed_path,
                "thumbnail_path": thumbnail_path,
            },
        )
        if result.rowcount == 0:
            raise ValueError(f"Video {video_id} is missing or not in PENDING state")


def set_video_failed(engine, video_id: int) -> None:
    query = text(
        """
        UPDATE videos
        SET status = 'FAILED'
        WHERE id = :video_id
        """
    )
    with engine.begin() as connection:
        connection.execute(query, {"video_id": video_id})


def process_message(engine, s3_client, payload: Dict) -> None:
    video_id = payload.get("video_id")
    raw_file_path = payload.get("raw_file_path")
    if video_id is None or not raw_file_path:
        raise ValueError("Payload must contain video_id and raw_file_path")

    source_bucket, source_key = parse_bucket_and_key(raw_file_path)
    processed_key = f"{video_id}/processed.mp4"
    thumbnail_key = f"{video_id}/thumbnail.jpg"

    with tempfile.TemporaryDirectory(prefix=f"transcoder-{video_id}-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_file = tmp_path / Path(source_key).name
        output_file = tmp_path / "processed.mp4"
        thumbnail_file = tmp_path / "thumbnail.jpg"

        logger.info("Downloading %s/%s", source_bucket, source_key)
        s3_client.download_file(source_bucket, source_key, str(input_file))

        run_transcode_ffmpeg(input_file, output_file)
        run_thumbnail_ffmpeg(output_file, thumbnail_file)

        s3_client.upload_file(str(output_file), PROCESSED_VIDEOS_BUCKET, processed_key)
        s3_client.upload_file(str(thumbnail_file), PROCESSED_VIDEOS_BUCKET, thumbnail_key)

        set_video_ready(
            engine=engine,
            video_id=int(video_id),
            processed_path=f"{PROCESSED_VIDEOS_BUCKET}/{processed_key}",
            thumbnail_path=f"{PROCESSED_VIDEOS_BUCKET}/{thumbnail_key}",
        )


def main() -> None:
    redis_client = get_redis_client()
    s3_client = get_s3_client()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    ensure_bucket_exists(s3_client, PROCESSED_VIDEOS_BUCKET)

    logger.info("Transcoder worker listening on '%s'", TRANSCODE_QUEUE)

    while True:
        video_id_for_failure = None
        try:
            item = redis_client.brpop(TRANSCODE_QUEUE, timeout=0)
            if not item:
                continue

            _, raw_payload = item
            payload = json.loads(raw_payload)
            video_id_for_failure = int(payload.get("video_id")) if payload.get("video_id") is not None else None
            process_message(engine, s3_client, payload)
            logger.info("Successfully processed job for video_id=%s", payload.get("video_id"))
        except Exception as exc:
            logger.exception("Failed to process transcode job: %s", exc)
            if video_id_for_failure is not None:
                try:
                    set_video_failed(engine, video_id_for_failure)
                except (SQLAlchemyError, ValueError):
                    logger.exception("Failed to mark video_id=%s as FAILED", video_id_for_failure)


if __name__ == "__main__":
    main()
