from datetime import datetime, timezone
from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    cash_balance: Mapped[float] = mapped_column(Numeric(20, 8), default=1000000)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class UserSession(Base):
    __tablename__ = 'user_sessions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Holding(Base):
    __tablename__ = 'holdings'
    __table_args__ = (UniqueConstraint('user_id', 'symbol', name='uq_holding_user_symbol'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    symbol: Mapped[str] = mapped_column(String)
    company_name: Mapped[str]
    sector: Mapped[str]
    quantity: Mapped[float] = mapped_column(Numeric(20, 6))
    average_price: Mapped[float] = mapped_column(Numeric(20, 8))


class Transaction(Base):
    __tablename__ = 'transactions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    symbol: Mapped[str]
    company_name: Mapped[str]
    transaction_type: Mapped[str]
    quantity: Mapped[float] = mapped_column(Numeric(20, 6))
    price: Mapped[float] = mapped_column(Numeric(20, 8))
    transaction_date: Mapped[datetime] = mapped_column(Date)
    realized_pnl: Mapped[float] = mapped_column(Numeric(20, 8), default=0)


class WatchlistItem(Base):
    __tablename__ = 'watchlist'
    __table_args__ = (UniqueConstraint('user_id', 'symbol', name='uq_watchlist_user_symbol'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    symbol: Mapped[str] = mapped_column(String)


class Metadata(Base):
    __tablename__ = 'metadata'
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
