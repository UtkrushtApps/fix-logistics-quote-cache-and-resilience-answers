#!/bin/bash
set -e

BASE_DIR=/root/task

echo "Stopping containers..."
docker compose -f "$BASE_DIR/docker-compose.yml" down --volumes --remove-orphans || true

echo "Removing Docker images..."
docker rmi -f task-app || true
docker rmi -f redis:7-alpine || true

echo "Pruning unused Docker resources..."
docker system prune -a --volumes -f

echo "Removing Python cache files..."
find "$BASE_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$BASE_DIR" -name '*.pyc' -delete 2>/dev/null || true
find "$BASE_DIR" -name '*.pyo' -delete 2>/dev/null || true
find "$BASE_DIR" -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
find "$BASE_DIR" -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true

echo "Removing Redis data directory..."
rm -rf "$BASE_DIR/data" || true

echo "Deleting task folder..."
rm -rf "$BASE_DIR"

echo "Cleanup completed successfully! Droplet is now clean."
