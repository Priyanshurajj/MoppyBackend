import math
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models import CleanerProfile, Booking, BookingStatus, UserRole
from app.features.bookings.schemas import BookingResponse
from app.features.cleaners.schemas import (
    LocationUpdateRequest,
    StatusUpdateRequest,
    CleanerProfileResponse,
    JobOtpRequest,
)

import random

from app.core.redis import redis_client

router = APIRouter(prefix="/api/cleaners", tags=["Cleaners"])

# ── Haversine Distance Helper ──
def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on the earth (specified in decimal degrees)"""
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371 # Radius of earth in kilometers
    return c * r


def require_cleaner(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Dependency to ensure the user is a cleaner and fetch their profile."""
    if user["role"] != UserRole.CLEANER.value:
        raise HTTPException(status_code=403, detail="Not authorized as cleaner")
    
    profile = db.query(CleanerProfile).filter(CleanerProfile.user_id == user["user_id"]).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Cleaner profile not found")
    
    return profile


@router.get("/me", response_model=CleanerProfileResponse)
def get_cleaner_profile(profile: CleanerProfile = Depends(require_cleaner)):
    """Get the active cleaner's profile stats and status."""
    return profile


@router.put("/location")
def update_location(
    request: LocationUpdateRequest,
    profile: CleanerProfile = Depends(require_cleaner),
    db: Session = Depends(get_db)
):
    """Update cleaner GPS coordinates in the background."""
    profile.current_lat = request.lat
    profile.current_lng = request.lng
    db.commit()
    
    # Also cache in Redis for fast tracking polls
    redis_key = f"cleaner:{profile.user_id}:location"
    redis_client.hset(redis_key, mapping={"lat": str(request.lat), "lng": str(request.lng)})
    redis_client.expire(redis_key, 300)  # 5 min TTL
    
    return {"message": "Location updated"}


@router.put("/status")
def update_status(
    request: StatusUpdateRequest,
    profile: CleanerProfile = Depends(require_cleaner),
    db: Session = Depends(get_db)
):
    """Go ONLINE, OFFLINE, or BUSY."""
    profile.current_status = request.status
    db.commit()
    return {"message": f"Status updated to {request.status}"}


@router.get("/jobs/available", response_model=list[BookingResponse])
def get_available_jobs(
    max_radius_km: float = 10.0,
    profile: CleanerProfile = Depends(require_cleaner),
    db: Session = Depends(get_db)
):
    """
    Dispatch Engine (MVP): Find all UNASSIGNED bookings within `max_radius_km`.
    In a production app, PostGIS or Celery would chunk this dynamically.
    """
    if profile.current_lat is None or profile.current_lng is None:
        return []

    unassigned_bookings = db.query(Booking).filter(
        Booking.status == BookingStatus.UNASSIGNED
    ).all()
    
    available_jobs = []
    for booking in unassigned_bookings:
        dist = haversine(
            profile.current_lat, profile.current_lng,
            booking.customer_lat, booking.customer_lng
        )
        if dist <= max_radius_km:
            available_jobs.append(booking)
            
    # Sort by closest first
    available_jobs.sort(key=lambda b: haversine(
        profile.current_lat, profile.current_lng,
        b.customer_lat, b.customer_lng
    ))
    
    return available_jobs


@router.get("/jobs/active", response_model=list[BookingResponse])
def get_active_jobs(
    profile: CleanerProfile = Depends(require_cleaner),
    db: Session = Depends(get_db)
):
    """Get jobs currently assigned to or in progress by this cleaner."""
    active = db.query(Booking).filter(
        Booking.cleaner_id == profile.user_id,
        Booking.status.in_([BookingStatus.ASSIGNED, BookingStatus.EN_ROUTE, BookingStatus.IN_PROGRESS])
    ).all()
    return active


@router.post("/jobs/{booking_id}/accept")
def accept_job(
    booking_id: int,
    profile: CleanerProfile = Depends(require_cleaner),
    db: Session = Depends(get_db)
):
    """Accept an available unassigned job."""
    # ENFORCE: Only 1 active job per cleaner
    active_job = db.query(Booking).filter(
        Booking.cleaner_id == profile.user_id,
        Booking.status.in_([BookingStatus.ASSIGNED, BookingStatus.EN_ROUTE, BookingStatus.IN_PROGRESS])
    ).first()
    
    if active_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="You already have an active job. Please complete it first."
        )

    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.status == BookingStatus.UNASSIGNED
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Job no longer available"
        )
        
    booking.cleaner_id = profile.user_id
    booking.status = BookingStatus.ASSIGNED
    booking.start_service_otp = str(random.randint(1000, 9999))
    db.commit()
    
    return {"message": "Job accepted successfully!", "booking_id": booking.id}

@router.post("/jobs/{booking_id}/start")
def start_job(
    booking_id: int,
    request: JobOtpRequest,
    profile: CleanerProfile = Depends(require_cleaner),
    db: Session = Depends(get_db)
):
    """Validate customer's Start OTP to begin cleaning."""
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.cleaner_id == profile.user_id,
        Booking.status == BookingStatus.ASSIGNED
    ).first()
    
    if not booking:
        raise HTTPException(404, "Assigned job not found")
        
    if booking.start_service_otp != request.otp:
        raise HTTPException(400, "Invalid Start OTP provided by customer")
        
    booking.status = BookingStatus.IN_PROGRESS
    booking.end_service_otp = str(random.randint(1000, 9999))
    db.commit()
    
    return {"message": "Job started!"}

@router.post("/jobs/{booking_id}/end")
def end_job(
    booking_id: int,
    request: JobOtpRequest,
    profile: CleanerProfile = Depends(require_cleaner),
    db: Session = Depends(get_db)
):
    """Validate customer's End OTP to complete cleaning."""
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.cleaner_id == profile.user_id,
        Booking.status == BookingStatus.IN_PROGRESS
    ).first()
    
    if not booking:
        raise HTTPException(404, "In-progress job not found")
        
    if booking.end_service_otp != request.otp:
        raise HTTPException(400, "Invalid End OTP provided by customer")
        
    booking.status = BookingStatus.COMPLETED
    profile.total_jobs += 1
    db.commit()
    
    return {"message": "Job completed successfully!"}
