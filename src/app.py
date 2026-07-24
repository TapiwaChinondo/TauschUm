from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import db_models
from .database import Base, SessionLocal, engine

app = FastAPI()

# Updated the app to load and work with a database so that users and items can persist when offline

# Create tables if needed and define entities
Base.metadata.create_all(bind=engine)


class UserCreate(BaseModel):
    username: str
    password: str
    address: str


class ItemCreate(BaseModel):
    name: str
    description: str | None = None
    photo_path: str | None = None
    owner_id: int

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


@app.post("/users")
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    db_user = db_models.User(
        username=user.username,
        password_hash=user.password,
        address=user.address,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.get("/users")
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


@app.get("/items")
def get_items(
    db: Session = Depends(get_db),
):
    return db.query(db_models.Item).all()