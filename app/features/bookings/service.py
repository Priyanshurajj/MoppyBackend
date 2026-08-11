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


import uuid

def calculate_total(service: Service, duration_mins: int) -> float:
    """Calculate the total price based on base + extra 30-min blocks."""
    extra_blocks = max(0, (duration_mins - service.estimated_time_mins)) // 30
    return service.base_price + (extra_blocks * service.price_per_30min)


def create_order_group(db: Session, user_id: int, data: dict):
    """Create an OrderGroup containing multiple Bookings from the cart."""
    from app.db.models import OrderGroup
    
    order_group_id = str(uuid.uuid4())
    total_amount = 0.0
    bookings = []
    
    for item in data["items"]:
        service = db.query(Service).filter(Service.id == item["service_id"]).first()
        if not service:
            raise ValueError(f"Service with ID {item['service_id']} not found")
            
        booking_total = calculate_total(service, item["duration_mins"])
        total_amount += booking_total
        
        booking = Booking(
            order_group_id=order_group_id,
            customer_id=user_id,
            service_id=item["service_id"],
            booking_type=BookingType(data["booking_type"]),
            duration_mins=item["duration_mins"],
            customer_address=data["customer_address"],
            customer_lat=data["customer_lat"],
            customer_lng=data["customer_lng"],
            scheduled_time=data.get("scheduled_time"),
            total_amount=booking_total,
            status=BookingStatus.PENDING,
            start_service_otp=generate_otp(),
            end_service_otp=generate_otp(),
        )
        bookings.append(booking)
        db.add(booking)
        
    order_group = OrderGroup(
        id=order_group_id,
        customer_id=user_id,
        total_amount=total_amount
    )
    db.add(order_group)
    db.commit()
    
    return order_group, bookings


def create_razorpay_order(db: Session, order_group) -> dict:
    """Create a Razorpay order and store it in our Payments table linked to the order_group."""
    amount_paise = int(order_group.total_amount * 100)

    order_data = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"moppy_order_{order_group.id[:8]}",
    })

    payment = Payment(
        order_group_id=order_group.id,
        razorpay_order_id=order_data["id"],
        amount=order_group.total_amount,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.commit()

    return {
        "order_group_id": order_group.id,
        "razorpay_order_id": order_data["id"],
        "amount": amount_paise,
        "currency": "INR",
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
    }


def verify_razorpay_payment(db: Session, data: dict) -> bool:
    """Verify Razorpay signature and update Bookings + Payment status."""
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

        bookings = db.query(Booking).filter(Booking.order_group_id == payment.order_group_id).all()
        for booking in bookings:
            booking.status = BookingStatus.UNASSIGNED  # Ready for dispatch

        db.commit()
        return True
    else:
        payment.status = PaymentStatus.FAILED
        db.commit()
        return False
