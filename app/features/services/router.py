from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Service
from app.features.services.schemas import ServiceResponse

router = APIRouter(prefix="/api/services", tags=["Services"])

@router.get("", response_model=list[ServiceResponse])
def get_services(db: Session = Depends(get_db)):
    """Fetch all active cleaning services."""
    services = db.query(Service).filter(Service.is_active == True).all()
    return services

@router.post("/seed", status_code=201)
def seed_services(db: Session = Depends(get_db)):
    """(Dev Only) Populates the database with default cleaning services."""
    if db.query(Service).count() > 0:
        return {"message": "Services already seeded!"}
        
    default_services = [
        {"name": "Bathroom cleaning", "description": "Deep cleaning of bathroom.", "base_price": 100.0, "original_price": 150.0, "price_per_30min": 100.0, "estimated_time_mins": 30},
        {"name": "Sweeping and mopping", "description": "Complete floor cleaning.", "base_price": 70.0, "original_price": 130.0, "price_per_30min": 70.0, "estimated_time_mins": 30},
        {"name": "Dusting and Wiping", "description": "Dusting of all surfaces.", "base_price": 75.0, "original_price": 140.0, "price_per_30min": 75.0, "estimated_time_mins": 30},
        {"name": "Utensils", "description": "Washing and drying utensils.", "base_price": 40.0, "original_price": 100.0, "price_per_30min": 40.0, "estimated_time_mins": 30},
        {"name": "Kitchen cleaning", "description": "Cleaning kitchen slabs, sink.", "base_price": 80.0, "original_price": 145.0, "price_per_30min": 80.0, "estimated_time_mins": 30},
        {"name": "Balcony", "description": "Balcony floor and railing cleaning.", "base_price": 80.0, "original_price": 150.0, "price_per_30min": 80.0, "estimated_time_mins": 30},
    ]
    
    for s in default_services:
        db.add(Service(**s))
    
    db.commit()
    return {"message": "Seed successful"}
