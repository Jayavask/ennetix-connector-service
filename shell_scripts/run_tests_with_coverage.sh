#!/bin/bash
# Run all tests with coverage report

echo "=========================================="
echo "Running P1 & P2 Tests with Coverage"
echo "=========================================="

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run tests with coverage
echo ""
echo "Running pytest with coverage..."
pytest tests/ \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml \
    -v

echo ""
echo "=========================================="
echo "Coverage Report Generated"
echo "=========================================="
echo "HTML report: htmlcov/index.html"
echo "XML report: coverage.xml"
echo ""

# Check if coverage meets threshold
COVERAGE=$(pytest tests/ --cov=app --cov-report=term --quiet 2>&1 | grep "TOTAL" | awk '{print $NF}' | sed 's/%//')
echo "Total Coverage: ${COVERAGE}%"

if (( $(echo "$COVERAGE >= 100" | bc -l) )); then
    echo "✅ Coverage meets 100% requirement!"
    exit 0
else
    echo "⚠️  Coverage is below 100%"
    exit 1
fi

