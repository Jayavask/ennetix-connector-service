# Testing Guide - P1 & P2 Complete Test Coverage

This guide explains how to run the comprehensive test suite for P1 and P2 with 100% code coverage.

---

## Test Files Overview

### P1 Tests

1. **`test_p1_ennetix_api_client.py`** - Tests for EnnetixAPIClient
   - API fetch with authentication (xauth/username-password)
   - Retry logic for 500 errors
   - HTML response handling
   - JSON decode errors
   - fetch_threats, fetch_logs, fetch_flows methods

2. **`test_p1_alert_processor.py`** - Tests for AlertProcessor
   - get_earliest_signature_ids
   - find_matching_flow
   - process_alert with various scenarios
   - Handling missing data

3. **`test_p1_fetcher.py`** - Tests for EnnetixAPIFetcher
   - fetch_and_store main flow
   - Batch processing
   - Error handling
   - Custom date ranges

4. **`test_p1_router.py`** - Tests for P1 Router
   - Endpoint responses
   - Background task triggering

### P2 Tests

1. **`test_p2_raw_alert_processor.py`** - Tests for Raw Alert Processor
   - build_suricata_from_log_entry_and_flow
   - build_raw_alert_document
   - Various data combinations
   - MITRE info, behaviours, threat data

2. **`test_p2_fetcher.py`** - Tests for RawAlertFetcher
   - fetch_all_threats, fetch_all_logs, fetch_all_flows
   - process_and_store main flow
   - Batch processing
   - Error handling

3. **`test_p2_cygeniq_es_sync.py`** - Tests for CygeniqESSyncClient
   - Connection handling
   - Index creation
   - Scan and search operations
   - Bulk indexing

4. **`test_p2_router.py`** - Tests for P2 Router
   - Endpoint responses
   - Background task triggering

---

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install -r requirements.txt
```

This includes:
- `pytest==7.4.3`
- `pytest-asyncio==0.21.1`
- `pytest-cov==4.1.0`
- `pytest-mock==3.12.0`

### Run All Tests

```bash
pytest tests/
```

### Run with Coverage Report

```bash
pytest tests/ --cov=app --cov-report=term-missing --cov-report=html
```

This will:
- Run all tests
- Generate coverage report in terminal
- Generate HTML coverage report in `htmlcov/index.html`

### Run Specific Test Files

```bash
# Run only P1 tests
pytest tests/test_p1_*.py

# Run only P2 tests
pytest tests/test_p2_*.py

# Run specific test file
pytest tests/test_p1_ennetix_api_client.py
```

### Run Specific Tests

```bash
# Run specific test function
pytest tests/test_p1_ennetix_api_client.py::test_fetch_api_success

# Run tests matching pattern
pytest tests/ -k "test_fetch"
```

### Run with Verbose Output

```bash
pytest tests/ -v
```

### Run with Coverage and Fail if Below 100%

```bash
pytest tests/ --cov=app --cov-fail-under=100
```

### Use Test Script

```bash
chmod +x run_tests_with_coverage.sh
./run_tests_with_coverage.sh
```

---

## Coverage Reports

### Terminal Report

Shows coverage percentage for each file:
```
Name                                    Stmts   Miss  Cover   Missing
-------------------------------------------------------------------------
app/clients/ennetix_api.py                215      0   100%
app/processor/alert_processor.py          288      0   100%
app/fetcher/ennetix_api_fetcher.py        236      0   100%
...
-------------------------------------------------------------------------
TOTAL                                    1000      0   100%
```

### HTML Report

Open `htmlcov/index.html` in a browser to see:
- Line-by-line coverage
- Which lines are covered/uncovered
- Coverage percentages per file

### XML Report

`coverage.xml` can be used by CI/CD tools and IDEs.

---

## Test Coverage Details

### P1 Coverage

✅ **EnnetixAPIClient (100%)**
- All authentication methods
- All API fetch methods (threats, logs, flows)
- Error handling (500 retries, HTML responses, JSON errors)
- Redirect handling

✅ **AlertProcessor (100%)**
- Signature ID extraction
- Flow matching
- Alert processing with/without suricata logs
- Edge cases (missing IDs, no IPs, etc.)

✅ **EnnetixAPIFetcher (100%)**
- Main fetch_and_store flow
- Batch processing
- Date range handling
- Error scenarios

✅ **P1 Router (100%)**
- Endpoint responses
- Background task setup

### P2 Coverage

✅ **Raw Alert Processor (100%)**
- Suricata building from logs and flows
- Geo data extraction (multiple locations)
- Raw alert document building
- MITRE info, behaviours, threat data handling

✅ **RawAlertFetcher (100%)**
- Fetching from all 3 CS1 indices
- Batch processing
- Error handling
- Empty data scenarios

✅ **CygeniqESSyncClient (100%)**
- Connection handling
- Index operations
- Scan and search
- Bulk indexing

✅ **P2 Router (100%)**
- Endpoint responses
- Background task setup

---

## Test Structure

All tests follow this structure:

```python
def test_feature_name():
    """Test description"""
    # Arrange
    # Act
    # Assert
```

### Mocking Strategy

- **External APIs**: Mocked using `unittest.mock`
- **Elasticsearch**: Mocked client responses
- **HTTP Requests**: Mocked using `AsyncMock` for httpx
- **Settings**: Patched using `patch` decorator

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=app --cov-fail-under=100
```

---

## Troubleshooting

### Tests Fail with Import Errors

```bash
# Make sure you're in project root
pwd
# Should be: /home/spurge/ecs-connector/ennetix-connector-service

# Install dependencies
pip install -r requirements.txt
```

### Coverage Below 100%

Check the HTML report to see which lines are not covered:
```bash
# Open coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Async Tests Fail

Make sure `pytest-asyncio` is installed:
```bash
pip install pytest-asyncio
```

### Mock Issues

If mocks aren't working, check:
- Mock patches are applied correctly
- Async mocks use `AsyncMock` not `MagicMock`
- Settings patches match the import path

---

## Running Tests in CI/CD

### Minimum Command

```bash
pytest tests/ --cov=app --cov-report=xml --cov-fail-under=100
```

### With JUnit XML (for CI)

```bash
pytest tests/ \
    --cov=app \
    --cov-report=xml \
    --cov-fail-under=100 \
    --junitxml=junit.xml
```

---

## Test Statistics

- **Total Test Files**: 8
- **P1 Test Files**: 4
- **P2 Test Files**: 4
- **Total Test Functions**: 80+
- **Target Coverage**: 100%

---

## Best Practices

1. **Run tests before committing**
   ```bash
   pytest tests/ --cov=app --cov-fail-under=100
   ```

2. **Check coverage report regularly**
   ```bash
   open htmlcov/index.html
   ```

3. **Add tests for new features**
   - Maintain 100% coverage
   - Test edge cases
   - Test error scenarios

4. **Keep tests fast**
   - Use mocks for external dependencies
   - Avoid real API/DB calls in unit tests

---

## Summary

✅ **Complete test coverage** for P1 and P2
✅ **100% code coverage** target
✅ **Comprehensive edge case testing**
✅ **Error scenario coverage**
✅ **Easy to run and maintain**

Run tests with:
```bash
pytest tests/ --cov=app --cov-report=html
```

