"""
Bookings feature — Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CreateBookingRequest(BaseModel):
    service_id: int
    booking_type: str  # "INSTANT" or "SCHEDULED"
    scheduled_time: Optional[datetime] = None
    duration_mins: int  # 30, 60, 90...
    customer_address: str
    customer_lat: float
    customer_lng: float


class BookingResponse(BaseModel):
    id: int
    customer_id: int
    service_id: int
    service_name: Optional[str] = None
    cleaner_id: Optional[int] = None
    cleaner_name: Optional[str] = None
    cleaner_profile_pic: Optional[str] = None
    cleaner_rating: Optional[float] = None
    booking_type: str
    status: str
    scheduled_time: Optional[datetime]
    duration_mins: int
    customer_address: str
    total_amount: float
    start_service_otp: Optional[str]
    end_service_otp: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RazorpayOrderResponse(BaseModel):
    booking_id: int
    razorpay_order_id: str
    amount: int  # In paise (₹499 = 49900)
    currency: str = "INR"
    razorpay_key_id: str


class PaymentVerifyRequest(BaseModel):
    booking_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
