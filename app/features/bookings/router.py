"""
Bookings feature — FastAPI router for booking creation, Razorpay order, and payment verification.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from datetime import datetime, timezone
from app.core.security import get_current_user
from app.db.models import Booking, BookingStatus, User
from app.features.bookings import service as booking_service
from app.features.bookings.schemas import (
    CreateBookingRequest,
    BookingResponse,
    RazorpayOrderResponse,
    PaymentVerifyRequest,
)

import asyncio

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])

async def auto_cancel_booking(db: Session, order_group_id: str):
    """Wait for 5 minutes and cancel unassigned bookings in the order."""
    await asyncio.sleep(300) # 5 minutes
    
    # Needs a fresh session because the old one might be closed
    from app.db.session import SessionLocal
    local_db = SessionLocal()
    try:
        bookings = local_db.query(Booking).filter(
            Booking.order_group_id == order_group_id,
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.UNASSIGNED])
        ).all()
        
        for booking in bookings:
            booking.status = BookingStatus.CANCELLED
            
        if bookings:
            local_db.commit()
    finally:
        local_db.close()


@router.post("", response_model=RazorpayOrderResponse)
def create_booking(
    request: CreateBookingRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new booking and return a Razorpay order for payment.
    Flow: Customer selects service → chooses time → hits Book → gets Razorpay checkout.
    """
    # ENFORCE: Only 1 active booking at a time
    active = db.query(Booking).filter(
        Booking.customer_id == current_user["user_id"],
        Booking.status.not_in([BookingStatus.COMPLETED, BookingStatus.CANCELLED, BookingStatus.PENDING])
    ).first()
    if active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="You already have an active booking. Please wait for it to complete."
        )

    try:
        order_group, bookings = booking_service.create_order_group(db, current_user["user_id"], request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    razorpay_order = booking_service.create_razorpay_order(db, order_group)
    
    # Spawn background task to auto-cancel if not accepted in 5 mins
    background_tasks.add_task(auto_cancel_booking, db, order_group.id)
    
    return razorpay_order


@router.post("/verify-payment")
def verify_payment(
    request: PaymentVerifyRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify Razorpay payment signature. If valid, booking status becomes UNASSIGNED."""
    is_valid = booking_service.verify_razorpay_payment(db, request.model_dump())
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment verification failed",
        )
    return {"message": "Payment verified successfully", "order_group_id": request.order_group_id}


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch a specific booking by ID."""
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.customer_id == current_user["user_id"],
    ).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@router.get("", response_model=list[BookingResponse])
def get_my_bookings(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch all bookings for the current user."""
    from sqlalchemy.orm import joinedload
    
    bookings = db.query(Booking).options(
        joinedload(Booking.service),
        joinedload(Booking.cleaner).joinedload(User.cleaner_profile)
    ).filter(
        Booking.customer_id == current_user["user_id"]
    ).order_by(Booking.created_at.desc()).all()

    response = []
    for b in bookings:
        b_dict = {c.name: getattr(b, c.name) for c in b.__table__.columns}
        b_dict["service_name"] = b.service.name if b.service else None
        if b.cleaner:
            b_dict["cleaner_name"] = b.cleaner.name
            b_dict["cleaner_profile_pic"] = b.cleaner.profile_pic
            b_dict["cleaner_rating"] = b.cleaner.cleaner_profile.rating if b.cleaner.cleaner_profile else None
        response.append(b_dict)

    return response

@router.post("/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a booking before cleaner is assigned."""
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.customer_id == current_user["user_id"]
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    if booking.status not in [BookingStatus.PENDING, BookingStatus.UNASSIGNED]:
        raise HTTPException(status_code=400, detail="Booking cannot be cancelled at this stage. Please contact support.")
        
    booking.status = BookingStatus.CANCELLED
    db.commit()
    return {"message": "Booking cancelled successfully"}
