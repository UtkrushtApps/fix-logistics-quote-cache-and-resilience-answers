from fastapi import FastAPI

from app.redis_client import get_redis_client, is_redis_available
from app.routes.api import router
from app.services.service import seed_shipping_rates

app = FastAPI(title="Logistics Quote Service")

app.include_router(router)


@app.on_event("startup")
async def startup_event():
    client = get_redis_client()
    seed_shipping_rates(client)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "redis": "ok" if is_redis_available() else "degraded",
    }
