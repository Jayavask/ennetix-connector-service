#!/bin/bash

echo "=========================================="
echo "Testing P2 Endpoint"
echo "=========================================="

# Test health first
echo ""
echo "1. Testing health endpoint..."
curl -s http://localhost:8000/health | jq . || echo "Service not running or jq not installed"

echo ""
echo "2. Triggering P2 sync..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/p2/sync \
  -H "Content-Type: application/json")

echo "$RESPONSE" | jq . || echo "$RESPONSE"

echo ""
echo "=========================================="
echo "✅ P2 sync triggered!"
echo "Check service logs for progress."
echo "=========================================="
