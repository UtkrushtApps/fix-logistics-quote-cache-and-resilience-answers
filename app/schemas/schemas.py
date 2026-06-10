from typing import Optional

from pydantic import BaseModel, Field


class ZonePricingUpdate(BaseModel):
    fuel_surcharge: float = Field(ge=0)
    handling_multiplier: float = Field(gt=0)


class QuoteResponse(BaseModel):
    origin: str
    destination: str
    service: str
    base_rate: float
    fuel_surcharge: float
    handling_multiplier: float
    total_quote: float
    zone_id: int


class ZoneConfigResponse(BaseModel):
    zone_id: int
    fuel_surcharge: float
    handling_multiplier: float
    last_updated: Optional[str] = None
