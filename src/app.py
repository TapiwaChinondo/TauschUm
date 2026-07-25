from fastapi import Depends, FastAPI, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from pathlib import Path
from uuid import uuid4

from . import db_models
from .database import Base, SessionLocal, engine

app = FastAPI()

# Connecting with front end
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define direcotry for images sued for item listings.
UPLOAD_DIRECTORY = Path(
    "frontend/images/uploads"
)

UPLOAD_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)

# Updated the app to load and work with a database so that users and items can persist when offline

# Create tables if needed and define entities
Base.metadata.create_all(bind=engine)


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    address: str

# Implementing a response so that passwords are not exposed 
class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    address: str

    model_config = {
        "from_attributes": True
    }


class ItemCreate(BaseModel):
    name: str
    description: str | None = None
    photo_path: str | None = None
    owner_id: int

# Display username by an item
class ItemResponse(BaseModel):
    id: int
    name: str
    description: str
    photo_path: str | None
    owner_id: int
    owner_username: str

# Logging in
class LoginRequest(BaseModel):
    username: str
    password: str

# Open a database session for each request and close it afterwards
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@app.get("/")
def home():
    return {
        "message": "Welcome to TauschUm!"
    }


@app.post("/users", response_model=UserResponse)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    # Prevent dupliate user names cleanly
    existing_user = db.query(db_models.User).filter(
        db_models.User.username == user.username
    ).first()

    # Error message 
    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="Username is already taken",
        )
    
    # Adding duplicate email check 
    existing_email = db.query(db_models.User).filter(
        db_models.User.email == user.email
    ).first()

    if existing_email is not None:
        raise HTTPException(
            status_code=409,
            detail="Email is already registered.",
        )
        
    db_user = db_models.User(
        username=user.username,
        email=user.email,
        password_hash=user.password,
        address=user.address,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.get("/users", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
):
    return db.query(db_models.User).all()


@app.post("/items")
def create_item(
    item: ItemCreate,
    db: Session = Depends(get_db),
):
    owner = db.query(db_models.User).filter(
        db_models.User.id == item.owner_id
    ).first()

    if owner is None:
        raise HTTPException(
            status_code=404,
            detail="Owner not found",
        )

    db_item = db_models.Item(
        name=item.name,
        description=item.description,
        photo_path=item.photo_path,
        owner_id=item.owner_id,
    )

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    return db_item


@app.get("/items", response_model=list[ItemResponse])
def get_items(db: Session = Depends(get_db)):
    items = db.query(db_models.Item).all()

    return [
        ItemResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            photo_path=item.photo_path,
            owner_id=item.owner_id,
            owner_username=item.owner.username,
        )
        for item in items
    ]

# Implementing logging in
@app.post("/login")
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = db.query(db_models.User).filter(
        db_models.User.username == login_data.username
    ).first()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
        )

    if user.password_hash != login_data.password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
        )

    return {
        "message": "Login successful",
        "username": user.username,
        "user_id": user.id,
    }


# Allow for uploading of new item listings with user's own iamges 
@app.post("/items/upload")
async def create_item_with_photo(
    name: str = Form(...),
    description: str = Form(...),
    owner_id: int = Form(...),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    owner = (
        db.query(db_models.User)
        .filter(
            db_models.User.id == owner_id
        )
        .first()
    )

    if owner is None:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    # For now only accept these 3 types of images, (Easier to handle)
    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    # Raise exceptions if not possible
    if photo.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "Photo must be a JPEG, PNG, "
                "or WebP image."
            ),
        )

    file_extension = Path(
        photo.filename or ""
    ).suffix.lower()

    # Unique file names are needed so that images are not owerwritten by other users.
    unique_filename = (
        f"{uuid4().hex}{file_extension}"
    )

    saved_file_path = (
        UPLOAD_DIRECTORY / unique_filename
    )

    photo_contents = await photo.read()

    with open(saved_file_path, "wb") as file:
        file.write(photo_contents)

    # Images added to this project look into limiting size 
    database_photo_path = (
        f"images/uploads/{unique_filename}"
    )

    # Add the new item to the database so it appears in the market place
    new_item = db_models.Item(
        name=name,
        description=description,
        photo_path=database_photo_path,
        owner_id=owner_id,
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return {
        "id": new_item.id,
        "name": new_item.name,
        "description": new_item.description,
        "photo_path": new_item.photo_path,
        "owner_id": new_item.owner_id,
        "owner_username": owner.username,
    }