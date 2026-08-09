from pydantic import BaseModel
from app.db.models import CleanerStatus

class LocationUpdateRequest(BaseModel):
    lat: float
    lng: float

class StatusUpdateRequest(BaseModel):
    status: CleanerStatus

class CleanerProfileResponse(BaseModel):
    is_verified: bool
    current_status: CleanerStatus
    current_lat: float | None
    current_lng: float | None
    rating: float
    total_jobs: int

    class Config:
        from_attributes = True

class JobOtpRequest(BaseModel):
    otp: str
