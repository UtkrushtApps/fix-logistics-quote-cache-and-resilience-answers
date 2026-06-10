#!/bin/bash
set -e

BASE_DIR=/root/task

echo "Starting logistics quote service..."
docker compose -f "$BASE_DIR/docker-compose.yml" up -d --build

echo "Waiting for Redis to be ready..."
for i in $(seq 1 20); do
  if docker compose -f "$BASE_DIR/docker-compose.yml" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "Redis is ready."
    break
  fi
  echo "  Waiting for Redis... ($i/20)"
  sleep 2
done

echo "Waiting for application to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "Application is ready."
    break
  fi
  echo "  Waiting for application... ($i/30)"
  sleep 2
done

echo "Validating Redis connectivity..."
REDIS_PING=$(docker compose -f "$BASE_DIR/docker-compose.yml" exec -T redis redis-cli ping 2>/dev/null || echo "FAILED")
if [ "$REDIS_PING" != "PONG" ]; then
  echo "ERROR: Redis is not responding."
  exit 1
fi
echo "Redis connectivity: OK"

echo "Validating application health..."
HEALTH=$(curl -sf http://127.0.0.1:8000/health || echo "FAILED")
if echo "$HEALTH" | grep -q "FAILED"; then
  echo "ERROR: Application health check failed."
  exit 1
fi
echo "Application health: OK"

echo "Seeding initial zone configuration data..."
curl -sf -X POST http://127.0.0.1:8000/admin/zones/7/pricing \
  -H 'Content-Type: application/json' \
  -d '{"fuel_surcharge": 0.12, "handling_multiplier": 1.08}' > /dev/null || true
curl -sf -X POST http://127.0.0.1:8000/admin/zones/3/pricing \
  -H 'Content-Type: application/json' \
  -d '{"fuel_surcharge": 0.09, "handling_multiplier": 1.05}' > /dev/null || true
curl -sf -X POST http://127.0.0.1:8000/admin/zones/12/pricing \
  -H 'Content-Type: application/json' \
  -d '{"fuel_surcharge": 0.15, "handling_multiplier": 1.12}' > /dev/null || true

echo ""
echo "Deployment complete. Service is running at http://127.0.0.1:8000"
echo "API docs available at http://127.0.0.1:8000/docs"
