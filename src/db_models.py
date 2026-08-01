from datetime import datetime
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

# Using SQL alchemy to produce the databse entitities

# User 
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    
    email: Mapped[str] = mapped_column(
    String(255),
    unique=True,
    nullable=False,
    )
    
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    items: Mapped[list["Item"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

# Item
class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    photo_path: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    
    listing_status: Mapped[str] = mapped_column(
        String(20),
        default="available",
        nullable=False,
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    owner: Mapped["User"] = relationship(
        back_populates="items",
    )

class TradeRequest(Base):
    __tablename__ = "trade_requests"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    
    parent_trade_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("trade_requests.id"),
        nullable=True,
    )

    requester: Mapped["User"] = relationship(
        foreign_keys=[requester_id],
    )

    receiver: Mapped["User"] = relationship(
        foreign_keys=[receiver_id],
    )

    offered_items: Mapped[list["TradeOfferedItem"]] = relationship(
        back_populates="trade_request",
        cascade="all, delete-orphan",
    )

    requested_items: Mapped[list["TradeRequestedItem"]] = relationship(
        back_populates="trade_request",
        cascade="all, delete-orphan",
    )


class TradeOfferedItem(Base):
    __tablename__ = "trade_offered_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    trade_request_id: Mapped[int] = mapped_column(
        ForeignKey("trade_requests.id"),
        nullable=False,
    )

    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id"),
        nullable=False,
    )

    trade_request: Mapped["TradeRequest"] = relationship(
        back_populates="offered_items",
    )

    item: Mapped["Item"] = relationship()


class TradeRequestedItem(Base):
    __tablename__ = "trade_requested_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    trade_request_id: Mapped[int] = mapped_column(
        ForeignKey("trade_requests.id"),
        nullable=False,
    )

    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id"),
        nullable=False,
    )

    trade_request: Mapped["TradeRequest"] = relationship(
        back_populates="requested_items",
    )

    item: Mapped["Item"] = relationship()