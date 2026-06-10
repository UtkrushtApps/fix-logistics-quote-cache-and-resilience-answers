import json
from dataclasses import replace
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from redis.exceptions import RedisError

from app.models.models import ShippingRate, ZoneConfig
from app.redis_client import get_redis_client

REDIS_KEY_PREFIX = "logistics"
QUOTE_CACHE_TTL_SECONDS = 300
ZONE_CONFIG_CACHE_TTL_SECONDS = 300


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SHIPPING_RATES_DB = [
    ShippingRate(origin="NYC", destination="BOS", service="express", base_rate=45.00, zone_id=7),
    ShippingRate(origin="NYC", destination="BOS", service="standard", base_rate=28.50, zone_id=7),
    ShippingRate(origin="NYC", destination="LAX", service="express", base_rate=120.00, zone_id=3),
    ShippingRate(origin="NYC", destination="LAX", service="standard", base_rate=75.00, zone_id=3),
    ShippingRate(origin="CHI", destination="MIA", service="express", base_rate=95.00, zone_id=12),
    ShippingRate(origin="CHI", destination="MIA", service="standard", base_rate=58.00, zone_id=12),
    ShippingRate(origin="SEA", destination="DEN", service="express", base_rate=82.00, zone_id=7),
    ShippingRate(origin="SEA", destination="DEN", service="standard", base_rate=51.00, zone_id=7),
]

_ZONE_CONFIG_DB_LOCK = Lock()
ZONE_CONFIG_DB = {
    7: ZoneConfig(zone_id=7, fuel_surcharge=0.12, handling_multiplier=1.08, last_updated=_utc_now_iso(), version=1),
    3: ZoneConfig(zone_id=3, fuel_surcharge=0.09, handling_multiplier=1.05, last_updated=_utc_now_iso(), version=1),
    12: ZoneConfig(zone_id=12, fuel_surcharge=0.15, handling_multiplier=1.12, last_updated=_utc_now_iso(), version=1),
}


def _normalize_location(value: str) -> str:
    return value.strip().upper()


def _normalize_service(value: str) -> str:
    return value.strip().lower()


def _rate_key(origin: str, destination: str, service: str) -> str:
    return f"{REDIS_KEY_PREFIX}:rate:{_normalize_location(origin)}:{_normalize_location(destination)}:{_normalize_service(service)}"


def _zone_config_key(zone_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}:zone:{zone_id}:config"


def _quote_cache_key(origin: str, destination: str, service: str, zone_id: int, zone_version: int) -> str:
    return (
        f"{REDIS_KEY_PREFIX}:quote:{_normalize_location(origin)}:{_normalize_location(destination)}:"
        f"{_normalize_service(service)}:zone:{zone_id}:v:{zone_version}"
    )


def _copy_zone_config(config: ZoneConfig) -> ZoneConfig:
    return replace(config)


def _serialize_rate(rate: ShippingRate) -> str:
    return json.dumps(
        {
            "origin": rate.origin,
            "destination": rate.destination,
            "service": rate.service,
            "base_rate": rate.base_rate,
            "zone_id": rate.zone_id,
        },
        separators=(",", ":"),
    )


def _serialize_zone_config(config: ZoneConfig) -> str:
    return json.dumps(
        {
            "zone_id": config.zone_id,
            "fuel_surcharge": config.fuel_surcharge,
            "handling_multiplier": config.handling_multiplier,
            "last_updated": config.last_updated,
            "version": config.version,
        },
        separators=(",", ":"),
    )


def _deserialize_zone_config(raw: str) -> ZoneConfig:
    payload = json.loads(raw)
    return ZoneConfig(
        zone_id=int(payload["zone_id"]),
        fuel_surcharge=float(payload["fuel_surcharge"]),
        handling_multiplier=float(payload["handling_multiplier"]),
        last_updated=payload.get("last_updated"),
        version=int(payload.get("version", 1)),
    )


def seed_shipping_rates(client):
    try:
        pipeline = client.pipeline(transaction=False)
        for rate in SHIPPING_RATES_DB:
            pipeline.set(_rate_key(rate.origin, rate.destination, rate.service), _serialize_rate(rate))

        with _ZONE_CONFIG_DB_LOCK:
            zone_configs = [_copy_zone_config(config) for config in ZONE_CONFIG_DB.values()]

        for zone_config in zone_configs:
            pipeline.set(
                _zone_config_key(zone_config.zone_id),
                _serialize_zone_config(zone_config),
                ex=ZONE_CONFIG_CACHE_TTL_SECONDS,
            )

        pipeline.execute()
    except RedisError:
        # Redis warming is best-effort only.
        return


def _lookup_rate_from_db(origin: str, destination: str, service: str) -> Optional[ShippingRate]:
    normalized_origin = _normalize_location(origin)
    normalized_destination = _normalize_location(destination)
    normalized_service = _normalize_service(service)

    for rate in SHIPPING_RATES_DB:
        if (
            rate.origin == normalized_origin
            and rate.destination == normalized_destination
            and rate.service == normalized_service
        ):
            return rate
    return None


def _lookup_zone_config_from_db(zone_id: int) -> Optional[ZoneConfig]:
    with _ZONE_CONFIG_DB_LOCK:
        config = ZONE_CONFIG_DB.get(zone_id)
        if config is None:
            return None
        return _copy_zone_config(config)


def get_zone_config(zone_id: int) -> Optional[ZoneConfig]:
    client = get_redis_client()

    try:
        cached = client.get(_zone_config_key(zone_id))
        if cached:
            try:
                return _deserialize_zone_config(cached)
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
    except RedisError:
        pass

    db_config = _lookup_zone_config_from_db(zone_id)
    if db_config is None:
        return None

    try:
        client.set(
            _zone_config_key(zone_id),
            _serialize_zone_config(db_config),
            ex=ZONE_CONFIG_CACHE_TTL_SECONDS,
        )
    except RedisError:
        pass

    return db_config


def get_shipping_quote(origin: str, destination: str, service: str):
    normalized_origin = _normalize_location(origin)
    normalized_destination = _normalize_location(destination)
    normalized_service = _normalize_service(service)

    rate = _lookup_rate_from_db(normalized_origin, normalized_destination, normalized_service)
    if rate is None:
        return None

    zone_config = get_zone_config(rate.zone_id)
    if zone_config is None:
        return None

    cache_key = _quote_cache_key(
        normalized_origin,
        normalized_destination,
        normalized_service,
        rate.zone_id,
        zone_config.version,
    )
    client = get_redis_client()

    try:
        cached = client.get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass
    except RedisError:
        pass

    total = rate.base_rate * zone_config.handling_multiplier * (1 + zone_config.fuel_surcharge)
    result = {
        "origin": normalized_origin,
        "destination": normalized_destination,
        "service": normalized_service,
        "base_rate": rate.base_rate,
        "fuel_surcharge": zone_config.fuel_surcharge,
        "handling_multiplier": zone_config.handling_multiplier,
        "total_quote": round(total, 2),
        "zone_id": rate.zone_id,
    }

    try:
        client.set(cache_key, json.dumps(result, separators=(",", ":")), ex=QUOTE_CACHE_TTL_SECONDS)
    except RedisError:
        pass

    return result


def update_zone_pricing(zone_id: int, fuel_surcharge: float, handling_multiplier: float):
    client = get_redis_client()
    last_updated = _utc_now_iso()

    with _ZONE_CONFIG_DB_LOCK:
        existing = ZONE_CONFIG_DB.get(zone_id)
        next_version = (existing.version + 1) if existing else 1
        updated_config = ZoneConfig(
            zone_id=zone_id,
            fuel_surcharge=fuel_surcharge,
            handling_multiplier=handling_multiplier,
            last_updated=last_updated,
            version=next_version,
        )
        ZONE_CONFIG_DB[zone_id] = updated_config

    try:
        client.set(
            _zone_config_key(zone_id),
            _serialize_zone_config(updated_config),
            ex=ZONE_CONFIG_CACHE_TTL_SECONDS,
        )
    except RedisError:
        # The in-memory DB remains authoritative when Redis is unavailable.
        pass
