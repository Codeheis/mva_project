import os
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

DB_URL = os.environ.get("DATABASE_URL") or (
    f"postgresql://{os.environ.get('DB_USER', 'postgres')}:"
    f"{os.environ.get('DB_PASSWORD', 'postgres')}@"
    f"{os.environ.get('DB_HOST', 'postgres')}:"
    f"{os.environ.get('DB_PORT', '5432')}/"
    f"{os.environ.get('DB_NAME', 'catalog')}"
)

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# SQLAlchemy models (schema: infrastructure/initdb/init.sql)
# ---------------------------------------------------------------------------


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

    comments = relationship("Comment", back_populates="video", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="video", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="comments")


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("video_id", "user_id", name="uq_likes_video_user"),)

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="likes")


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_video_or_404(video_id: int, db: Session) -> Video:
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


def require_user_id(user_id: Optional[int]) -> int:
    if user_id is None or user_id < 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid user_id is required",
        )
    return user_id


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class VideoCreate(BaseModel):
    uploader_id: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    thumbnail_path: Optional[str] = None
    raw_file_path: Optional[str] = None
    processed_path: Optional[str] = None
    status: str = "pending"


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uploader_id: int
    title: str
    description: Optional[str]
    thumbnail_path: Optional[str]
    raw_file_path: Optional[str]
    processed_path: Optional[str]
    status: str
    created_at: datetime


class CommentCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    content: str = Field(..., min_length=1)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    user_id: int
    content: str
    created_at: datetime


class LikeToggle(BaseModel):
    user_id: int = Field(..., ge=1)


class LikeToggleOut(BaseModel):
    liked: bool
    like_count: int


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Catalog Service",
    root_path="/api/catalog",
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
    return {"status": "ok", "service": "catalog"}


@app.post("/videos", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
def create_video(video: VideoCreate, db: Session = Depends(get_db)):
    # TODO: Verify token with Auth Service; use authenticated user as uploader_id
    uploader_id = require_user_id(video.uploader_id)

    db_video = Video(
        uploader_id=uploader_id,
        title=video.title,
        description=video.description or None,
        thumbnail_path=video.thumbnail_path,
        raw_file_path=video.raw_file_path,
        processed_path=video.processed_path,
        status=video.status,
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video


@app.get("/videos", response_model=List[VideoOut])
def list_videos(
    search: Optional[str] = Query(None, description="Filter videos by title (case-insensitive)"),
    uploader_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Video)
    if search:
        query = query.filter(Video.title.ilike(f"%{search}%"))
    if uploader_id is not None:
        query = query.filter(Video.uploader_id == uploader_id)
        return query.order_by(Video.created_at.desc()).all()
    return query.order_by(Video.created_at.desc()).limit(10).all()


@app.delete("/videos/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    db.delete(video)
    db.commit()
    return {"message": "Video deleted successfully"}


@app.get("/videos/{video_id}", response_model=VideoOut)
def get_video(video_id: int, db: Session = Depends(get_db)):
    return get_video_or_404(video_id, db)


@app.post(
    "/videos/{video_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def post_comment(
    video_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
):
    # TODO: Verify token with Auth Service; use authenticated user as user_id
    user_id = require_user_id(comment.user_id)
    get_video_or_404(video_id, db)

    db_comment = Comment(video_id=video_id, user_id=user_id, content=comment.content)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment


@app.get("/videos/{video_id}/comments", response_model=List[CommentOut])
def get_comments(video_id: int, db: Session = Depends(get_db)):
    get_video_or_404(video_id, db)
    return (
        db.query(Comment)
        .filter(Comment.video_id == video_id)
        .order_by(Comment.created_at.asc())
        .all()
    )


@app.post("/videos/{video_id}/like", response_model=LikeToggleOut)
def toggle_like(
    video_id: int,
    body: LikeToggle,
    db: Session = Depends(get_db),
):
    # TODO: Verify token with Auth Service; use authenticated user as user_id
    user_id = require_user_id(body.user_id)
    get_video_or_404(video_id, db)

    existing = (
        db.query(Like)
        .filter(Like.video_id == video_id, Like.user_id == user_id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        liked = False
    else:
        db.add(Like(video_id=video_id, user_id=user_id))
        db.commit()
        liked = True

    like_count = db.query(Like).filter(Like.video_id == video_id).count()
    return LikeToggleOut(liked=liked, like_count=like_count)
