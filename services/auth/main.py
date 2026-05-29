import os
import logging
from fastapi import FastAPI, Depends, HTTPException, status, Body, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
from pydantic import BaseModel, EmailStr, ValidationError
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta ,timezone
from fastapi import Request

# Configuration
logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get("SECRET_KEY", "supersecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
DB_URL = os.environ.get("DB_URL") or (
    f"postgresql://{os.environ.get('DB_USER','postgres')}:"
    f"{os.environ.get('DB_PASSWORD','postgres')}@"
    f"{os.environ.get('DB_HOST','localhost')}:"
    f"{os.environ.get('DB_PORT','5432')}/"
    f"{os.environ.get('DB_NAME','auth')}"
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
http_bearer = HTTPBearer(auto_error=False)
Base = declarative_base()

# SQLAlchemy Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(150), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    bio = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    followers = relationship(
        "Subscription", foreign_keys="Subscription.leader_id", back_populates="leader"
    )
    following = relationship(
        "Subscription", foreign_keys="Subscription.follower_id", back_populates="follower"
    )

class Subscription(Base):
    __tablename__ = "subscriptions"
    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    leader_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    leader = relationship("User", foreign_keys=[leader_id], back_populates="followers")

# Pydantic Schemas
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserProfile(BaseModel):
    id: int
    username: str
    email: EmailStr
    bio: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True

class ProfileUpdateRequest(BaseModel):
    username: Optional[str] = None
    bio: Optional[str] = None
    password: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    bio: Optional[str] = None
    password: Optional[str] = None


class SubscriptionOut(BaseModel):
    leader_id: int
    username: str

# DB Session
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI app
app = FastAPI(root_path="/api/auth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth Utilities
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)



def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    # 2. Use timezone.utc to be explicit
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    # 3. Ensure 'sub' is a string
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if user and verify_password(password, user.password_hash):
        return user
    # try email login as well
    user = get_user_by_email(db, username)
    if user and verify_password(password, user.password_hash):
        return user
    return None

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id = int(user_id)
    except (JWTError, TypeError, ValueError):
        raise credentials_exception
    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    return user

# Create tables
Base.metadata.create_all(bind=engine)

# Endpoints

@app.post("/register", response_model=UserProfile)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if get_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        username=data.username,
        email=data.email,
        password_hash=get_password_hash(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.put("/update-profile", response_model=UserProfile)
def update_profile_put(
    payload: UserUpdate,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id = token_payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        user_id = int(user_id)
    except (JWTError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    current_user = get_user_by_id(db, user_id)
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    updated = False
    if payload.username and payload.username != current_user.username:
        if get_user_by_username(db, payload.username):
            raise HTTPException(status_code=400, detail="Username already taken")
        current_user.username = payload.username
        updated = True
    if payload.email and payload.email != current_user.email:
        if get_user_by_email(db, str(payload.email)):
            raise HTTPException(status_code=400, detail="Email already registered")
        current_user.email = str(payload.email)
        updated = True
    if payload.bio is not None:
        current_user.bio = payload.bio
        updated = True
    if payload.password:
        current_user.password_hash = pwd_context.hash(payload.password)
        updated = True

    if updated:
        db.commit()
        db.refresh(current_user)
    return current_user


@app.patch("/profile", response_model=UserProfile)
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = False
    if payload.username and payload.username != current_user.username:
        if get_user_by_username(db, payload.username):
            raise HTTPException(status_code=400, detail="Username already taken")
        current_user.username = payload.username
        updated = True
    if payload.bio is not None:
        current_user.bio = payload.bio
        updated = True
    if payload.password:
        current_user.password_hash = get_password_hash(payload.password)
        updated = True
    if updated:
        db.commit()
        db.refresh(current_user)
    return current_user

@app.post("/subscribe/{user_id}", status_code=201)
def subscribe(
    user_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot subscribe to yourself")
    leader = get_user_by_id(db, user_id)
    if not leader:
        raise HTTPException(status_code=404, detail="User not found")
    sub = db.query(Subscription).filter_by(follower_id=current_user.id, leader_id=user_id).first()
    if sub:
        raise HTTPException(status_code=409, detail="Already subscribed")
    sub = Subscription(follower_id=current_user.id, leader_id=user_id)
    db.add(sub)
    db.commit()
    return {"detail": "Subscribed"}

@app.get("/subscriptions", response_model=List[SubscriptionOut])
def list_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subs = (
        db.query(User.id.label("leader_id"), User.username)
        .join(Subscription, Subscription.leader_id == User.id)
        .filter(Subscription.follower_id == current_user.id)
        .all()
    )
    return [{"leader_id": s.leader_id, "username": s.username} for s in subs]

@app.get("/verify")
def verify(
    request: Request, # Add this to get access to raw headers
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db),
):

    # Print the headers to the container logs
    print(f"DEBUG: Incoming Headers: {request.headers}")
    """
    Internal endpoint. Returns user info in token or 401.
    """
    if credentials is None:
        logger.warning("Verify failed: missing Authorization header")
        raise HTTPException(status_code=401, detail="Invalid token")
    if credentials.scheme.lower() != "bearer":
        logger.warning("Verify failed: unsupported auth scheme '%s'", credentials.scheme)
        raise HTTPException(status_code=401, detail="Invalid token")

    token = credentials.credentials
    token_preview = f"{token[:10]}..." if token else "<empty>"
    logger.info("Verify request received token prefix: %s", token_preview)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM],options={"verify_exp": False})
       
        # DEBUG: Print the payload so you can see the 'exp' value
        print(f"DEBUG: Decoded Payload: {payload}")

        user_id = payload.get("sub")
        if user_id is None:
            logger.warning("Verify failed: token decoded but missing 'sub' claim")
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(user_id)
    except (JWTError, TypeError, ValueError) as exc:
        logger.warning("Verify failed: JWTError while decoding token (%s)", exc.__class__.__name__)
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_id(db, user_id)
    if not user:
        logger.warning("Verify failed: user not found for sub=%s", user_id)
        raise HTTPException(status_code=401, detail="User not found")
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "bio": user.bio,
        "created_at": user.created_at.isoformat(),
    }
