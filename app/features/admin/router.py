from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Booking

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/bookings")
def get_all_bookings(db: Session = Depends(get_db)):
    """
    Returns all bookings across the platform for the Admin UI.
    Security: In a real app, this requires an admin JWT validation. 
    For MVP testing, we are leaving this unprotected to quickly boot the dashboard.
    """
    bookings = db.query(Booking).order_by(Booking.created_at.desc()).all()
    
    result = []
    for b in bookings:
        result.append({
            "id": b.id,
            "status": b.status.value if hasattr(b.status, 'value') else str(b.status), # Enums vs Strings safely
            "created_at": b.created_at.isoformat(),
            "customer_id": b.customer_id,
            "customer_address": b.customer_address,
            "total_amount": b.total_amount,
            "cleaner_id": b.cleaner_id,
            "payment_status": b.payment.status.value if b.payment else "N/A"
        })
    return result
