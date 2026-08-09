import sys
import os

# Add backend to path so imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from app.db.session import SessionLocal
from app.db.models import Booking, Payment

def clear_test_data():
    db = SessionLocal()
    try:
        # Delete payments first due to foreign keys (if any)
        payments_deleted = db.query(Payment).delete()
        bookings_deleted = db.query(Booking).delete()
        db.commit()
        print(f"✅ Success! Deleted {bookings_deleted} bookings and {payments_deleted} payments from the database.")
    except Exception as e:
        db.rollback()
        print(f"❌ Error deleting data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_test_data()
