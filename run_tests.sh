#!/bin/bash
# Test script to verify the service works correctly

echo "=========================================="
echo "Testing ENNETIX Connector Service"
echo "=========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    exit 1
fi
echo "✅ .env file exists"

# Check Python version
python_version=$(python3 --version 2>&1)
echo "✅ Python version: $python_version"

# Test imports
echo ""
echo "Testing imports..."
python3 test_imports.py
if [ $? -ne 0 ]; then
    echo "❌ Import test failed!"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ All basic tests passed!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Install dependencies: pip install -r requirements.txt"
echo "2. Start the service: python3 -m app.main"
echo "3. Test P1 endpoint: curl -X POST http://localhost:8000/api/v1/p1/sync"
echo ""

