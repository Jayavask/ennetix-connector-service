<!-- Summary: How to Run and Verify P1 & P2 Code -->
<!-- Quick verification -->

1. Syntax check (already done):
 python3 test_simple.py
    Result: All 26 Python files have valid syntax.
2. Install dependencies:
    pip install -r requirements.txt
3. Test imports:
    python3 test_imports.py
4. Verify logic preservation:
    python3 verify_logic.py
5. Start the service:
    python3 -m app.main

<!-- Test P1 endpoint: -->
curl --location 'http://localhost:8000/api/v1/p1/sync' \
--header 'Content-Type: application/json' \
--data '{
    "start_date": "2025-11-26T06:45:53.000Z",
    "end_date": "2025-12-26T21:00:00.000Z"
  }'

<!-- Test P2 endpoint: -->
curl --location --request POST 'http://localhost:8000/api/v1/p2/sync' \
--header 'Content-Type: application/json'

<!-- Running tests -->
# Install dependencies (if not already installed)
pip install -r requirements.txt
# Run all tests with coverage
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
# Or use the script
chmod +x run_tests_with_coverage.sh
./run_tests_with_coverage.sh