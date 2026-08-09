"""
Auth feature — Business logic for OTP send/verify and user creation.
"""

import random
from sqlalchemy.orm import Session

from app.core.redis import redis_client
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.models import User, UserRole, CleanerProfile

settings = get_settings()


def generate_otp() -> str:
    """Generate a random 4-digit OTP."""
    return str(random.randint(1000, 9999))


def send_otp(phone: str) -> str:
    """
    Generate OTP, store in Redis with TTL, and dispatch via SMS provider.
    In development mode (SMS_PROVIDER=console), just prints OTP to terminal.
    Returns the OTP for dev convenience.
    """
    otp = generate_otp()

    # Store in Redis with 5-minute expiry
    redis_key = f"otp:{phone}"
    redis_client.setex(redis_key, settings.OTP_EXPIRE_SECONDS, otp)

    # Send OTP via configured provider
    if settings.SMS_PROVIDER == "console":
        print(f"\n{'='*40}")
        print(f"  📱 OTP for {phone}: {otp}")
        print(f"{'='*40}\n")
    else:
        # TODO: Integrate Fast2SMS / MSG91 / Twilio here
        pass

    return otp


def verify_otp(phone: str, otp: str) -> bool:
    """Validate the OTP against what is stored in Redis."""
    redis_key = f"otp:{phone}"
    stored_otp = redis_client.get(redis_key)

    if stored_otp and stored_otp == otp:
        redis_client.delete(redis_key)  # One-time use
        return True
    return False


def get_or_create_user(db: Session, phone: str, is_cleaner: bool = False) -> tuple[User, bool]:
    """
    Find existing user by phone or create a new one.
    If is_cleaner=True, upgrade role to CLEANER and provision CleanerProfile.
    """
    user = db.query(User).filter(User.phone == phone).first()
    is_new = False
    
    if not user:
        role = UserRole.CLEANER if is_cleaner else UserRole.CUSTOMER
        user = User(phone=phone, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        is_new = True
    elif is_cleaner and user.role != UserRole.CLEANER:
        user.role = UserRole.CLEANER
        db.commit()
        db.refresh(user)
        
    if is_cleaner:
        profile = db.query(CleanerProfile).filter(CleanerProfile.user_id == user.id).first()
        if not profile:
            profile = CleanerProfile(user_id=user.id)
            db.add(profile)
            db.commit()

    return user, is_new


def create_user_token(user: User) -> str:
    """Create a JWT access token embedding user_id and role."""
    return create_access_token(
        data={"user_id": user.id, "role": user.role.value}
    )
