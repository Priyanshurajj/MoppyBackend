"""
Auth feature — Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel


class SendOtpRequest(BaseModel):
    phone: str  # e.g. "+919876543210"


class SendOtpResponse(BaseModel):
    message: str
    phone: str


class VerifyOtpRequest(BaseModel):
    phone: str
    otp: str | None = None
    id_token: str | None = None
    is_cleaner_app: bool = False


class VerifyOtpResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    is_new_user: bool


class UserAddressResponse(BaseModel):
    id: int
    tag: str | None
    address: str
    lat: float | None
    lng: float | None
    is_default: bool

    class Config:
        from_attributes = True


class UserAddressCreate(BaseModel):
    tag: str | None = None
    address: str
    lat: float | None = None
    lng: float | None = None
    is_default: bool = False


class UserProfile(BaseModel):
    id: int
    phone: str
    name: str | None
    email: str | None
    role: str
    address: str | None
    city: str | None
    profile_pic: str | None
    addresses: list[UserAddressResponse] = []

    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    profile_pic: str | None = None
