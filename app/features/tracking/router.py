"""
Tracking API: Real-time cleaner location for customers.
Uses Redis for fast, high-frequency location caching.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.core.redis import redis_client
from app.db.models import Booking, BookingStatus, CleanerProfile

router = APIRouter(prefix="/api/bookings", tags=["Tracking"])


@router.get("/{booking_id}/tracking")
def get_cleaner_tracking(
    booking_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Customer polls this endpoint to get the assigned cleaner's latest location.
    Returns lat/lng from Redis (fast) with fallback to Postgres.
    """
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.customer_id == user["user_id"],
        Booking.status.in_([BookingStatus.ASSIGNED, BookingStatus.IN_PROGRESS])
    ).first()

    if not booking:
        raise HTTPException(404, "Active booking not found")

    if not booking.cleaner_id:
        raise HTTPException(404, "No cleaner assigned yet")

    # Try Redis first (fastest)
    redis_key = f"cleaner:{booking.cleaner_id}:location"
    cached = redis_client.hgetall(redis_key)

    if cached and "lat" in cached and "lng" in cached:
        lat = float(cached["lat"])
        lng = float(cached["lng"])
    else:
        # Fallback to Postgres
        profile = db.query(CleanerProfile).filter(
            CleanerProfile.user_id == booking.cleaner_id
        ).first()
        if not profile or profile.current_lat is None:
            raise HTTPException(404, "Cleaner location not available")
        lat = profile.current_lat
        lng = profile.current_lng

    # Get cleaner profile for details
    profile = db.query(CleanerProfile).filter(
        CleanerProfile.user_id == booking.cleaner_id
    ).first()

    return {
        "cleaner_lat": lat,
        "cleaner_lng": lng,
        "cleaner_name": f"Cleaner #{booking.cleaner_id}",
        "cleaner_rating": float(profile.rating) if profile else 4.5,
        "cleaner_total_jobs": profile.total_jobs if profile else 0,
        "booking_status": booking.status.value,
        "customer_lat": booking.customer_lat,
        "customer_lng": booking.customer_lng,
        "actual_start_time": booking.actual_start_time.isoformat() if booking.actual_start_time else None,
        "duration_mins": booking.duration_mins,
    }
