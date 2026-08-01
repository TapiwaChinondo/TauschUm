from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

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

# Define directory for images used for item listings.
UPLOAD_DIRECTORY = Path(
    "frontend/images/uploads"
)

UPLOAD_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)

# Create tables if needed and define entities.
Base.metadata.create_all(bind=engine)


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    address: str


# Implementing a response so that passwords are not exposed.
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


# Display username by an item.
class ItemResponse(BaseModel):
    id: int
    name: str
    description: str | None
    photo_path: str | None
    owner_id: int
    owner_username: str


# Logging in.
class LoginRequest(BaseModel):
    username: str
    password: str


class TradeRequestCreate(BaseModel):
    requester_id: int
    receiver_id: int
    offered_item_ids: list[int]
    requested_item_ids: list[int]


class TradeActionRequest(BaseModel):
    user_id: int


class CounterTradeRequestCreate(BaseModel):
    user_id: int
    offered_item_ids: list[int]
    requested_item_ids: list[int]


class TradeItemResponse(BaseModel):
    id: int
    name: str
    description: str | None
    photo_path: str | None
    owner_id: int
    owner_username: str


class TradeRequestResponse(BaseModel):
    id: int
    requester_id: int
    requester_username: str
    receiver_id: int
    receiver_username: str
    status: str
    created_at: datetime
    parent_trade_request_id: int | None
    offered_items: list[TradeItemResponse]
    requested_items: list[TradeItemResponse]


# Open a database session for each request and close it afterwards.
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_user_or_404(
    db: Session,
    user_id: int,
    detail: str = "User not found.",
):
    user = (
        db.query(db_models.User)
        .filter(db_models.User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail=detail,
        )

    return user


def get_trade_or_404(
    db: Session,
    trade_request_id: int,
):
    trade_request = (
        db.query(db_models.TradeRequest)
        .filter(
            db_models.TradeRequest.id == trade_request_id
        )
        .first()
    )

    if trade_request is None:
        raise HTTPException(
            status_code=404,
            detail="Trade request not found.",
        )

    return trade_request


def validate_trade_items(
    db: Session,
    requester_id: int,
    receiver_id: int,
    offered_item_ids: list[int],
    requested_item_ids: list[int],
):
    offered_item_ids = list(set(offered_item_ids))
    requested_item_ids = list(set(requested_item_ids))

    if len(offered_item_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="You must offer at least one item.",
        )

    if len(requested_item_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="You must request at least one item.",
        )

    if set(offered_item_ids) & set(requested_item_ids):
        raise HTTPException(
            status_code=400,
            detail=(
                "The same item cannot be both offered "
                "and requested."
            ),
        )

    offered_items = (
        db.query(db_models.Item)
        .filter(
            db_models.Item.id.in_(offered_item_ids)
        )
        .all()
    )

    if len(offered_items) != len(offered_item_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more offered items were not found.",
        )

    for item in offered_items:
        if item.owner_id != requester_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    "You can only offer items "
                    "that belong to you."
                ),
            )

        if item.listing_status != "available":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{item.name} is no longer available "
                    "for trading."
                ),
            )

    requested_items = (
        db.query(db_models.Item)
        .filter(
            db_models.Item.id.in_(requested_item_ids)
        )
        .all()
    )

    if len(requested_items) != len(requested_item_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more requested items were not found.",
        )

    for item in requested_items:
        if item.owner_id != receiver_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    "All requested items must belong "
                    "to the trade receiver."
                ),
            )

        if item.listing_status != "available":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{item.name} is no longer available "
                    "for trading."
                ),
            )

    return (
        offered_item_ids,
        requested_item_ids,
        offered_items,
        requested_items,
    )


def create_trade_record(
    db: Session,
    requester_id: int,
    receiver_id: int,
    offered_item_ids: list[int],
    requested_item_ids: list[int],
    parent_trade_request_id: int | None = None,
):
    trade_request = db_models.TradeRequest(
        requester_id=requester_id,
        receiver_id=receiver_id,
        status="pending",
        parent_trade_request_id=parent_trade_request_id,
    )

    db.add(trade_request)
    db.flush()

    for item_id in offered_item_ids:
        db.add(
            db_models.TradeOfferedItem(
                trade_request_id=trade_request.id,
                item_id=item_id,
            )
        )

    for item_id in requested_item_ids:
        db.add(
            db_models.TradeRequestedItem(
                trade_request_id=trade_request.id,
                item_id=item_id,
            )
        )

    return trade_request


def trade_to_response(
    trade_request: db_models.TradeRequest,
):
    return TradeRequestResponse(
        id=trade_request.id,
        requester_id=trade_request.requester_id,
        requester_username=trade_request.requester.username,
        receiver_id=trade_request.receiver_id,
        receiver_username=trade_request.receiver.username,
        status=trade_request.status,
        created_at=trade_request.created_at,
        parent_trade_request_id=(
            trade_request.parent_trade_request_id
        ),
        offered_items=[
            TradeItemResponse(
                id=link.item.id,
                name=link.item.name,
                description=link.item.description,
                photo_path=link.item.photo_path,
                owner_id=link.item.owner_id,
                owner_username=link.item.owner.username,
            )
            for link in trade_request.offered_items
        ],
        requested_items=[
            TradeItemResponse(
                id=link.item.id,
                name=link.item.name,
                description=link.item.description,
                photo_path=link.item.photo_path,
                owner_id=link.item.owner_id,
                owner_username=link.item.owner.username,
            )
            for link in trade_request.requested_items
        ],
    )


def trade_item_ids(
    trade_request: db_models.TradeRequest,
):
    return {
        link.item_id
        for link in trade_request.offered_items
    } | {
        link.item_id
        for link in trade_request.requested_items
    }


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
    existing_user = db.query(db_models.User).filter(
        db_models.User.username == user.username
    ).first()

    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="Username is already taken",
        )

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
    owner = get_user_or_404(
        db,
        item.owner_id,
        "Owner not found",
    )

    db_item = db_models.Item(
        name=item.name,
        description=item.description,
        photo_path=item.photo_path,
        owner_id=item.owner_id,
        listing_status="available",
    )

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    return db_item


@app.get("/items", response_model=list[ItemResponse])
def get_items(db: Session = Depends(get_db)):
    items = (
        db.query(db_models.Item)
        .filter(
            db_models.Item.listing_status == "available"
        )
        .all()
    )

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


# View an individual active listing.
@app.get("/items/{item_id}", response_model=ItemResponse)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = (
        db.query(db_models.Item)
        .filter(
            db_models.Item.id == item_id,
            db_models.Item.listing_status == "available",
        )
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found or no longer available.",
        )

    return ItemResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        photo_path=item.photo_path,
        owner_id=item.owner_id,
        owner_username=item.owner.username,
    )


# View your own active listings.
@app.get(
    "/users/{user_id}/items",
    response_model=list[ItemResponse],
)
def get_user_items(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, user_id)

    items = (
        db.query(db_models.Item)
        .filter(
            db_models.Item.owner_id == user_id,
            db_models.Item.listing_status == "available",
        )
        .all()
    )

    return [
        ItemResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            photo_path=item.photo_path,
            owner_id=item.owner_id,
            owner_username=user.username,
        )
        for item in items
    ]


# Implementing logging in.
@app.post("/login")
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = db.query(db_models.User).filter(
        db_models.User.username == login_data.username
    ).first()

    if user is None or user.password_hash != login_data.password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
        )

    return {
        "message": "Login successful",
        "username": user.username,
        "user_id": user.id,
    }


# Allow uploading new item listings with the user's own images.
@app.post("/items/upload")
async def create_item_with_photo(
    name: str = Form(...),
    description: str = Form(...),
    owner_id: int = Form(...),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    owner = get_user_or_404(db, owner_id)

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

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

    unique_filename = (
        f"{uuid4().hex}{file_extension}"
    )

    saved_file_path = (
        UPLOAD_DIRECTORY / unique_filename
    )

    photo_contents = await photo.read()

    with open(saved_file_path, "wb") as file:
        file.write(photo_contents)

    database_photo_path = (
        f"images/uploads/{unique_filename}"
    )

    new_item = db_models.Item(
        name=name,
        description=description,
        photo_path=database_photo_path,
        owner_id=owner_id,
        listing_status="available",
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
    
# Allow for removal of items
@app.patch("/items/{item_id}/remove")
def remove_listing(
    item_id: int,
    user_data: TradeActionRequest,
    db: Session = Depends(get_db),
):
    item = (
        db.query(db_models.Item)
        .filter(db_models.Item.id == item_id)
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Listing was not found.",
        )

    if item.owner_id != user_data.user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only remove your own listings.",
        )

    if item.listing_status != "available":
        raise HTTPException(
            status_code=400,
            detail="This listing is no longer available.",
        )

    conflicting_trade_ids = {
        offered_item.trade_request_id
        for offered_item in db.query(
            db_models.TradeOfferedItem
        ).filter(
            db_models.TradeOfferedItem.item_id == item_id
        ).all()
    }

    conflicting_trade_ids.update(
        requested_item.trade_request_id
        for requested_item in db.query(
            db_models.TradeRequestedItem
        ).filter(
            db_models.TradeRequestedItem.item_id == item_id
        ).all()
    )

    if conflicting_trade_ids:
        pending_trades = (
            db.query(db_models.TradeRequest)
            .filter(
                db_models.TradeRequest.id.in_(
                    conflicting_trade_ids
                ),
                db_models.TradeRequest.status == "pending",
            )
            .all()
        )

        for trade in pending_trades:
            trade.status = "unavailable"

    item.listing_status = "removed"

    try:
        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not remove the listing.",
        )

    return {
        "message": "Listing removed successfully.",
        "item_id": item.id,
    }


# Create a new trade request.
@app.post(
    "/trade-requests",
    response_model=TradeRequestResponse,
)
def create_trade_request(
    trade_data: TradeRequestCreate,
    db: Session = Depends(get_db),
):
    if trade_data.requester_id == trade_data.receiver_id:
        raise HTTPException(
            status_code=400,
            detail="You cannot send a trade request to yourself.",
        )

    get_user_or_404(
        db,
        trade_data.requester_id,
        "Requester was not found.",
    )
    get_user_or_404(
        db,
        trade_data.receiver_id,
        "Trade receiver was not found.",
    )

    (
        offered_item_ids,
        requested_item_ids,
        _,
        _,
    ) = validate_trade_items(
        db=db,
        requester_id=trade_data.requester_id,
        receiver_id=trade_data.receiver_id,
        offered_item_ids=trade_data.offered_item_ids,
        requested_item_ids=trade_data.requested_item_ids,
    )

    try:
        trade_request = create_trade_record(
            db=db,
            requester_id=trade_data.requester_id,
            receiver_id=trade_data.receiver_id,
            offered_item_ids=offered_item_ids,
            requested_item_ids=requested_item_ids,
        )

        db.commit()
        db.refresh(trade_request)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create the trade request.",
        )

    return trade_to_response(trade_request)


# Trade requests received by a user.
@app.get(
    "/users/{user_id}/trade-requests/received",
    response_model=list[TradeRequestResponse],
)
def get_received_trade_requests(
    user_id: int,
    db: Session = Depends(get_db),
):
    get_user_or_404(db, user_id)

    trade_requests = (
        db.query(db_models.TradeRequest)
        .filter(
            db_models.TradeRequest.receiver_id == user_id
        )
        .order_by(
            db_models.TradeRequest.created_at.desc()
        )
        .all()
    )

    return [
        trade_to_response(trade_request)
        for trade_request in trade_requests
    ]


# Trade requests sent by a user.
@app.get(
    "/users/{user_id}/trade-requests/sent",
    response_model=list[TradeRequestResponse],
)
def get_sent_trade_requests(
    user_id: int,
    db: Session = Depends(get_db),
):
    get_user_or_404(db, user_id)

    trade_requests = (
        db.query(db_models.TradeRequest)
        .filter(
            db_models.TradeRequest.requester_id == user_id
        )
        .order_by(
            db_models.TradeRequest.created_at.desc()
        )
        .all()
    )

    return [
        trade_to_response(trade_request)
        for trade_request in trade_requests
    ]


# Accepting a trade immediately completes it for this prototype.
@app.patch(
    "/trade-requests/{trade_request_id}/accept",
    response_model=TradeRequestResponse,
)
def accept_trade_request(
    trade_request_id: int,
    action: TradeActionRequest,
    db: Session = Depends(get_db),
):
    trade_request = get_trade_or_404(
        db,
        trade_request_id,
    )

    if action.user_id != trade_request.receiver_id:
        raise HTTPException(
            status_code=403,
            detail="Only the trade receiver can accept this request.",
        )

    if trade_request.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending trade requests can be accepted.",
        )

    item_ids = trade_item_ids(trade_request)

    try:
        # Re-check the ownership and availability immediately before acceptance.
        validate_trade_items(
            db=db,
            requester_id=trade_request.requester_id,
            receiver_id=trade_request.receiver_id,
            offered_item_ids=[
                link.item_id
                for link in trade_request.offered_items
            ],
            requested_item_ids=[
                link.item_id
                for link in trade_request.requested_items
            ],
        )

        # Any other pending request containing one of these items can no
        # longer be completed.
        other_pending_trades = (
            db.query(db_models.TradeRequest)
            .filter(
                db_models.TradeRequest.status == "pending",
                db_models.TradeRequest.id != trade_request.id,
            )
            .all()
        )

        for other_trade in other_pending_trades:
            if trade_item_ids(other_trade) & item_ids:
                other_trade.status = "unavailable"

        trade_request.status = "accepted"

        traded_items = (
            db.query(db_models.Item)
            .filter(db_models.Item.id.in_(item_ids))
            .all()
        )

        for item in traded_items:
            item.listing_status = "traded"

        db.commit()
        db.refresh(trade_request)

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not accept the trade request.",
        )

    return trade_to_response(trade_request)


@app.patch(
    "/trade-requests/{trade_request_id}/decline",
    response_model=TradeRequestResponse,
)
def decline_trade_request(
    trade_request_id: int,
    action: TradeActionRequest,
    db: Session = Depends(get_db),
):
    trade_request = get_trade_or_404(
        db,
        trade_request_id,
    )

    if action.user_id != trade_request.receiver_id:
        raise HTTPException(
            status_code=403,
            detail="Only the trade receiver can decline this request.",
        )

    if trade_request.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending trade requests can be declined.",
        )

    trade_request.status = "declined"
    db.commit()
    db.refresh(trade_request)

    return trade_to_response(trade_request)


@app.patch(
    "/trade-requests/{trade_request_id}/cancel",
    response_model=TradeRequestResponse,
)
def cancel_trade_request(
    trade_request_id: int,
    action: TradeActionRequest,
    db: Session = Depends(get_db),
):
    trade_request = get_trade_or_404(
        db,
        trade_request_id,
    )

    if action.user_id != trade_request.requester_id:
        raise HTTPException(
            status_code=403,
            detail="Only the requester can cancel this trade.",
        )

    if trade_request.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending trade requests can be cancelled.",
        )

    trade_request.status = "cancelled"
    db.commit()
    db.refresh(trade_request)

    return trade_to_response(trade_request)


@app.post(
    "/trade-requests/{trade_request_id}/counter",
    response_model=TradeRequestResponse,
)
def counter_trade_request(
    trade_request_id: int,
    counter_data: CounterTradeRequestCreate,
    db: Session = Depends(get_db),
):
    original_trade = get_trade_or_404(
        db,
        trade_request_id,
    )

    if counter_data.user_id != original_trade.receiver_id:
        raise HTTPException(
            status_code=403,
            detail="Only the receiver can counter this trade request.",
        )

    if original_trade.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending trade requests can be countered.",
        )

    # The previous receiver becomes the requester in the counter-offer.
    counter_requester_id = original_trade.receiver_id
    counter_receiver_id = original_trade.requester_id

    (
        offered_item_ids,
        requested_item_ids,
        _,
        _,
    ) = validate_trade_items(
        db=db,
        requester_id=counter_requester_id,
        receiver_id=counter_receiver_id,
        offered_item_ids=counter_data.offered_item_ids,
        requested_item_ids=counter_data.requested_item_ids,
    )

    try:
        original_trade.status = "countered"

        counter_trade = create_trade_record(
            db=db,
            requester_id=counter_requester_id,
            receiver_id=counter_receiver_id,
            offered_item_ids=offered_item_ids,
            requested_item_ids=requested_item_ids,
            parent_trade_request_id=original_trade.id,
        )

        db.commit()
        db.refresh(counter_trade)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create the counter-offer.",
        )

    return trade_to_response(counter_trade)
