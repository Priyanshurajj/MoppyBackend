from pydantic import BaseModel

class ServiceResponse(BaseModel):
    id: int
    name: str
    description: str | None
    base_price: float
    original_price: float | None = None
    price_per_30min: float
    estimated_time_mins: int
    is_active: bool

    class Config:
        from_attributes = True
