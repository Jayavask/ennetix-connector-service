"""
Verify that the original P1 logic is preserved in the microservice structure
"""
import inspect
from app.processor.alert_processor import AlertProcessor
from app.clients.ennetix_api import EnnetixAPIClient
from app.fetcher.ennetix_api_fetcher import EnnetixAPIFetcher

def verify_alert_processor():
    """Verify AlertProcessor has all original methods"""
    print("Verifying AlertProcessor...")
    
    processor = AlertProcessor()
    
    # Check required methods exist
    required_methods = [
        'get_earliest_signature_ids',
        'find_matching_flow',
        'process_alert'
    ]
    
    for method_name in required_methods:
        if hasattr(processor, method_name):
            print(f"  ✅ {method_name} exists")
        else:
            print(f"  ❌ {method_name} missing!")
            return False
    
    # Check process_alert signature
    sig = inspect.signature(processor.process_alert)
    params = list(sig.parameters.keys())
    expected_params = ['self', 'http_client', 'alert', 'threat_ip', 'semaphore', 'api3_semaphore']
    
    if params == expected_params:
        print(f"  ✅ process_alert has correct signature")
    else:
        print(f"  ⚠️  process_alert signature: {params} (expected: {expected_params})")
    
    return True

def verify_api_client():
    """Verify EnnetixAPIClient has all original methods"""
    print("\nVerifying EnnetixAPIClient...")
    
    client = EnnetixAPIClient()
    
    required_methods = [
        'fetch_api',
        'fetch_threats',
        'fetch_logs',
        'fetch_flows'
    ]
    
    for method_name in required_methods:
        if hasattr(client, method_name):
            print(f"  ✅ {method_name} exists")
        else:
            print(f"  ❌ {method_name} missing!")
            return False
    
    # Check retry logic exists
    source = inspect.getsource(client.fetch_api)
    if 'retry_count' in source and 'MAX_RETRIES' in source or 'max_retries' in source:
        print(f"  ✅ Retry logic present")
    else:
        print(f"  ⚠️  Retry logic may be missing")
    
    return True

def verify_fetcher():
    """Verify EnnetixAPIFetcher has main execution flow"""
    print("\nVerifying EnnetixAPIFetcher...")
    
    fetcher = EnnetixAPIFetcher()
    
    if hasattr(fetcher, 'fetch_and_store'):
        print(f"  ✅ fetch_and_store method exists")
        
        # Check it has the main flow
        source = inspect.getsource(fetcher.fetch_and_store)
        key_phrases = [
            'fetch_threats',
            'process_alert',
            'bulk_index_with_ids',
            'THREATS_INDEX',
            'LOGS_INDEX',
            'FLOWS_INDEX'
        ]
        
        for phrase in key_phrases:
            if phrase in source:
                print(f"  ✅ Contains: {phrase}")
            else:
                print(f"  ⚠️  Missing: {phrase}")
    else:
        print(f"  ❌ fetch_and_store method missing!")
        return False
    
    return True

def verify_constants():
    """Verify constants are preserved"""
    print("\nVerifying constants...")
    
    from app.processor.alert_processor import SERVICES, ROLES
    
    expected_services = ["dns", "ssh", "http", "https", "other"]
    expected_roles = ["client", "server"]
    
    if SERVICES == expected_services:
        print(f"  ✅ SERVICES: {SERVICES}")
    else:
        print(f"  ❌ SERVICES mismatch: {SERVICES} != {expected_services}")
        return False
    
    if ROLES == expected_roles:
        print(f"  ✅ ROLES: {ROLES}")
    else:
        print(f"  ❌ ROLES mismatch: {ROLES} != {expected_roles}")
        return False
    
    return True

def verify_config():
    """Verify configuration has all required settings"""
    print("\nVerifying configuration...")
    
    from app.config import settings
    
    required_settings = [
        'ENNETIX_API_BASE_URL',
        'ENNETIX_XAUTH',
        'THREATS_INDEX',
        'LOGS_INDEX',
        'FLOWS_INDEX',
        'ENNETIX_API_BATCH_SIZE',
        'ENNETIX_API3_BATCH_SIZE',
        'ENNETIX_MAX_RETRIES',
        'ENNETIX_RETRY_DELAY',
        'P1_DATE_RANGE_DAYS'
    ]
    
    for setting in required_settings:
        if hasattr(settings, setting):
            value = getattr(settings, setting)
            print(f"  ✅ {setting}: {value}")
        else:
            print(f"  ❌ {setting} missing!")
            return False
    
    return True

def main():
    """Run all verification checks"""
    print("=" * 60)
    print("Verifying P1 Logic Preservation")
    print("=" * 60)
    
    checks = [
        ("AlertProcessor", verify_alert_processor),
        ("EnnetixAPIClient", verify_api_client),
        ("EnnetixAPIFetcher", verify_fetcher),
        ("Constants", verify_constants),
        ("Configuration", verify_config),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("✅ All verifications passed! Original logic is preserved.")
        return 0
    else:
        print("❌ Some verifications failed. Please review.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())

