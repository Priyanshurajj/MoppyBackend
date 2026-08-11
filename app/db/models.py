"""
SQLAlchemy models for the entire application.
All tables are defined here so Alembic can auto-detect them.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from app.db.session import Base


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────
class UserRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    CLEANER = "CLEANER"
    ADMIN = "ADMIN"


class BookingType(str, enum.Enum):
    INSTANT = "INSTANT"
    SCHEDULED = "SCHEDULED"


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    EN_ROUTE = "EN_ROUTE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class CleanerStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    BUSY = "BUSY"


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(15), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    email = Column(String(150), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    address = Column(Text, nullable=True) # Legacy single address, will migrate to user_addresses
    city = Column(String(50), nullable=True)
    profile_pic = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    cleaner_profile = relationship("CleanerProfile", back_populates="user", uselist=False)
    bookings = relationship("Booking", back_populates="customer", foreign_keys="Booking.customer_id")
    addresses = relationship("UserAddress", back_populates="user", cascade="all, delete-orphan")


class UserAddress(Base):
    __tablename__ = "user_addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tag = Column(String(50), nullable=True) # e.g. Home, Work, Other
    address = Column(Text, nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="addresses")


class CleanerProfile(Base):
    __tablename__ = "cleaner_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    is_verified = Column(Boolean, default=False)
    current_status = Column(Enum(CleanerStatus), default=CleanerStatus.OFFLINE)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    rating = Column(Float, default=0.0)
    total_jobs = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="cleaner_profile")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    base_price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)  # Crossed price
    price_per_30min = Column(Float, nullable=False)  # For time-based pricing
    estimated_time_mins = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OrderGroup(Base):
    __tablename__ = "order_groups"

    id = Column(String(100), primary_key=True)  # uuid
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    customer = relationship("User", foreign_keys=[customer_id])
    bookings = relationship("Booking", back_populates="order_group")
    payment = relationship("Payment", back_populates="order_group", uselist=False)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    order_group_id = Column(String(100), ForeignKey("order_groups.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cleaner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)

    booking_type = Column(Enum(BookingType), nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING)

    scheduled_time = Column(DateTime, nullable=True)  # For SCHEDULED bookings
    actual_start_time = Column(DateTime, nullable=True) # For Live Timer
    duration_mins = Column(Integer, nullable=False)  # 30, 60, 90 etc.

    customer_address = Column(Text, nullable=False)
    customer_lat = Column(Float, nullable=False)
    customer_lng = Column(Float, nullable=False)

    start_service_otp = Column(String(4), nullable=True)
    end_service_otp = Column(String(4), nullable=True)

    total_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    order_group = relationship("OrderGroup", back_populates="bookings")
    customer = relationship("User", back_populates="bookings", foreign_keys=[customer_id])
    cleaner = relationship("User", foreign_keys=[cleaner_id])
    service = relationship("Service")
    payment = relationship("Payment", back_populates="booking", uselist=False)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), unique=True, nullable=True) # Legacy or single booking
    order_group_id = Column(String(100), ForeignKey("order_groups.id"), unique=True, nullable=True) # Cart bookings
    
    razorpay_order_id = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    razorpay_signature = Column(String(200), nullable=True)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    booking = relationship("Booking", back_populates="payment")
    order_group = relationship("OrderGroup", back_populates="payment")
