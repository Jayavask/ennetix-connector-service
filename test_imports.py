"""
Quick test script to verify all imports work correctly
"""
import sys

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from app.config import settings
        print("✅ app.config imported successfully")
        print(f"   - ENNETIX_API_BASE_URL: {settings.ENNETIX_API_BASE_URL}")
        print(f"   - THREATS_INDEX: {settings.THREATS_INDEX}")
    except Exception as e:
        print(f"❌ Failed to import app.config: {e}")
        return False
    
    try:
        from app.clients.ennetix_api import EnnetixAPIClient
        print("✅ app.clients.ennetix_api imported successfully")
    except Exception as e:
        print(f"❌ Failed to import app.clients.ennetix_api: {e}")
        return False
    
    try:
        from app.clients.cygeniq_es import CygeniqESClient
        print("✅ app.clients.cygeniq_es imported successfully")
    except Exception as e:
        print(f"❌ Failed to import app.clients.cygeniq_es: {e}")
        return False
    
    try:
        from app.processor.alert_processor import AlertProcessor
        print("✅ app.processor.alert_processor imported successfully")
    except Exception as e:
        print(f"❌ Failed to import app.processor.alert_processor: {e}")
        return False
    
    try:
        from app.fetcher.ennetix_api_fetcher import EnnetixAPIFetcher
        print("✅ app.fetcher.ennetix_api_fetcher imported successfully")
    except Exception as e:
        print(f"❌ Failed to import app.fetcher.ennetix_api_fetcher: {e}")
        return False
    
    try:
        from app.router.p1_router import router
        print("✅ app.router.p1_router imported successfully")
    except Exception as e:
        print(f"❌ Failed to import app.router.p1_router: {e}")
        return False
    
    try:
        from app.main import app
        print("✅ app.main imported successfully")
    except Exception as e:
        print(f"❌ Failed to import app.main: {e}")
        return False
    
    print("\n✅ All imports successful!")
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)

