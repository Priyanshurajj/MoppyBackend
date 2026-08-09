"""
Bookings feature — Business logic for creating bookings and Razorpay orders.
"""

import random
import razorpay
import hmac
import hashlib

from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.models import Booking, Service, Payment, BookingType, BookingStatus, PaymentStatus

settings = get_settings()

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def generate_otp() -> str:
    return str(random.randint(1000, 9999))


def calculate_total(service: Service, duration_mins: int) -> float:
    """Calculate the total price based on base + extra 30-min blocks."""
    extra_blocks = max(0, (duration_mins - service.estimated_time_mins)) // 30
    return service.base_price + (extra_blocks * service.price_per_30min)


def create_booking(db: Session, user_id: int, data: dict) -> Booking:
    """Create a new booking with start/end OTPs and calculated price."""
    service = db.query(Service).filter(Service.id == data["service_id"]).first()
    if not service:
        raise ValueError("Service not found")

    total = calculate_total(service, data["duration_mins"])

    booking = Booking(
        customer_id=user_id,
        service_id=data["service_id"],
        booking_type=BookingType(data["booking_type"]),
        duration_mins=data["duration_mins"],
        customer_address=data["customer_address"],
        customer_lat=data["customer_lat"],
        customer_lng=data["customer_lng"],
        scheduled_time=data.get("scheduled_time"),
        total_amount=total,
        status=BookingStatus.PENDING,
        start_service_otp=generate_otp(),
        end_service_otp=generate_otp(),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def create_razorpay_order(db: Session, booking: Booking) -> dict:
    """Create a Razorpay order and store the order_id in our Payments table."""
    amount_paise = int(booking.total_amount * 100)

    order_data = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"moppy_booking_{booking.id}",
    })

    payment = Payment(
        booking_id=booking.id,
        razorpay_order_id=order_data["id"],
        amount=booking.total_amount,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.commit()

    return {
        "booking_id": booking.id,
        "razorpay_order_id": order_data["id"],
        "amount": amount_paise,
        "currency": "INR",
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
    }


def verify_razorpay_payment(db: Session, data: dict) -> bool:
    """Verify Razorpay signature and update Booking + Payment status."""
    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{data['razorpay_order_id']}|{data['razorpay_payment_id']}".encode(),
        hashlib.sha256,
    ).hexdigest()

    payment = db.query(Payment).filter(
        Payment.razorpay_order_id == data["razorpay_order_id"]
    ).first()

    if not payment:
        return False

    if hmac.compare_digest(generated_signature, data["razorpay_signature"]):
        payment.razorpay_payment_id = data["razorpay_payment_id"]
        payment.razorpay_signature = data["razorpay_signature"]
        payment.status = PaymentStatus.SUCCESS

        booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
        if booking:
            booking.status = BookingStatus.UNASSIGNED  # Ready for dispatch

        db.commit()
        return True
    else:
        payment.status = PaymentStatus.FAILED
        db.commit()
        return False
