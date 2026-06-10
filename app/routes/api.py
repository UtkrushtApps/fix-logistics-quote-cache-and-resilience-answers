from fastapi import APIRouter, HTTPException

from app.schemas.schemas import QuoteResponse, ZoneConfigResponse, ZonePricingUpdate
from app.services.service import get_shipping_quote, get_zone_config, update_zone_pricing

router = APIRouter()


@router.get("/api/quotes", response_model=QuoteResponse)
def quote(origin: str, destination: str, service: str):
    result = get_shipping_quote(origin, destination, service)
    if result is None:
        raise HTTPException(status_code=404, detail="No rate found for this route")
    return result


@router.get("/api/zones/{zone_id}/config", response_model=ZoneConfigResponse)
def zone_config(zone_id: int):
    config = get_zone_config(zone_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Zone config not found")
    return config


@router.post("/admin/zones/{zone_id}/pricing")
def admin_update_zone_pricing(zone_id: int, payload: ZonePricingUpdate):
    update_zone_pricing(zone_id, payload.fuel_surcharge, payload.handling_multiplier)
    return {"status": "updated", "zone_id": zone_id}
