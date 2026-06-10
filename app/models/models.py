from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ShippingRate:
    origin: str
    destination: str
    service: str
    base_rate: float
    zone_id: int


@dataclass
class ZoneConfig:
    zone_id: int
    fuel_surcharge: float
    handling_multiplier: float
    last_updated: Optional[str] = None
    version: int = 1
