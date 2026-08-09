"""
Auth feature — FastAPI router with send-otp, verify-otp, and me endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.features.auth import service as auth_service
from app.features.auth.schemas import (
    SendOtpRequest,
    SendOtpResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
    UserProfile,
    ProfileUpdateRequest,
    UserAddressCreate,
    UserAddressResponse
)
from app.db.models import User, UserAddress

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/send-otp", response_model=SendOtpResponse)
def send_otp(request: SendOtpRequest):
    """
    Generate a 4-digit OTP and store it in Redis with a 5-min TTL.
    In dev mode, OTP is printed to the terminal console.
    """
    auth_service.send_otp(request.phone)
    return SendOtpResponse(
        message="OTP sent successfully", phone=request.phone
    )


@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp(request: VerifyOtpRequest, db: Session = Depends(get_db)):
    """
    Validate OTP from Redis. If valid, create/fetch user and return JWT.
    """
    is_valid = auth_service.verify_otp(request.phone, request.otp)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP",
        )

    user, is_new_user = auth_service.get_or_create_user(db, request.phone, request.is_cleaner_app)
    token = auth_service.create_user_token(user)

    return VerifyOtpResponse(
        access_token=token,
        user_id=user.id,
        role=user.role.value,
        is_new_user=is_new_user,
    )


@router.get("/me", response_model=UserProfile)
def get_me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the profile of the currently authenticated user.
    Requires a valid JWT in the Authorization header.
    """
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.put("/me", response_model=UserProfile)
def update_me(
    request: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if request.name is not None:
        user.name = request.name
    if request.email is not None:
        user.email = request.email
    if request.profile_pic is not None:
        user.profile_pic = request.profile_pic

    db.commit()
    db.refresh(user)
    return user


@router.get("/me/addresses", response_model=list[UserAddressResponse])
def get_my_addresses(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    addresses = db.query(UserAddress).filter(UserAddress.user_id == current_user["user_id"]).all()
    return addresses


@router.post("/me/addresses", response_model=UserAddressResponse)
def add_address(
    request: UserAddressCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # If this is set to default, unset other defaults
    if request.is_default:
        db.query(UserAddress).filter(UserAddress.user_id == current_user["user_id"]).update({"is_default": False})

    new_address = UserAddress(
        user_id=current_user["user_id"],
        tag=request.tag,
        address=request.address,
        lat=request.lat,
        lng=request.lng,
        is_default=request.is_default,
    )
    db.add(new_address)
    db.commit()
    db.refresh(new_address)
    return new_address


@router.put("/me/addresses/{address_id}/default", response_model=UserAddressResponse)
def set_default_address(
    address_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address = db.query(UserAddress).filter(
        UserAddress.id == address_id,
        UserAddress.user_id == current_user["user_id"]
    ).first()
    
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    db.query(UserAddress).filter(UserAddress.user_id == current_user["user_id"]).update({"is_default": False})
    address.is_default = True
    db.commit()
    db.refresh(address)
    return address


@router.delete("/me/addresses/{address_id}")
def delete_address(
    address_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address = db.query(UserAddress).filter(
        UserAddress.id == address_id,
        UserAddress.user_id == current_user["user_id"]
    ).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
        
    db.delete(address)
    db.commit()
    return {"message": "Address deleted"}
