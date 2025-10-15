#!/usr/bin/env python3
"""
Test script to verify the Trakt AI List Generator setup
Run this script to check if all components are working correctly
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment_variables():
    """Test if all required environment variables are set"""
    required_vars = [
        'TRAKT_CLIENT_ID',
        'TRAKT_CLIENT_SECRET', 
        'TRAKT_REDIRECT_URI',
        'GEMINI_API_KEY',
        'TMDB_API_KEY'
    ]
    
    print("🔍 Checking environment variables...")
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            print(f"❌ {var} is not set")
        else:
            print(f"✅ {var} is set")
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("\n✅ All required environment variables are set")
        return True

def test_imports():
    """Test if all required modules can be imported"""
    print("\n🔍 Testing module imports...")
    
    try:
        from api.trakt_auth import TraktAuth
        print("✅ TraktAuth imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import TraktAuth: {e}")
        return False
    
    try:
        from api.recommendation_engine import RecommendationEngine
        print("✅ RecommendationEngine imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import RecommendationEngine: {e}")
        return False
    
    try:
        from api.tmdb_client import TMDBClient
        print("✅ TMDBClient imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import TMDBClient: {e}")
        return False
    
    try:
        from api.history_fetcher import HistoryFetcher
        print("✅ HistoryFetcher imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import HistoryFetcher: {e}")
        return False
    
    try:
        from api.trakt_list import TraktListManager
        print("✅ TraktListManager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import TraktListManager: {e}")
        return False
    
    return True

def test_api_connections():
    """Test API connections (without making actual requests)"""
    print("\n🔍 Testing API client initialization...")
    
    try:
        from api.tmdb_client import TMDBClient
        tmdb = TMDBClient()
        if tmdb.api_key:
            print("✅ TMDB client initialized successfully")
        else:
            print("❌ TMDB API key not found")
            return False
    except Exception as e:
        print(f"❌ TMDB client initialization failed: {e}")
        return False
    
    try:
        from api.recommendation_engine import RecommendationEngine
        engine = RecommendationEngine()
        if engine.model:
            print("✅ Gemini client initialized successfully")
        else:
            print("❌ Gemini API key not found")
            return False
    except Exception as e:
        print(f"❌ Gemini client initialization failed: {e}")
        return False
    
    try:
        from api.trakt_auth import TraktAuth
        auth = TraktAuth()
        if auth.client_id and auth.client_secret:
            print("✅ Trakt auth client initialized successfully")
        else:
            print("❌ Trakt credentials not found")
            return False
    except Exception as e:
        print(f"❌ Trakt auth client initialization failed: {e}")
        return False
    
    return True

def test_redis_connection():
    """Test Redis connection"""
    print("\n🔍 Testing Redis connection...")
    
    try:
        import redis
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            client.ping()
            print("✅ Redis connection successful")
            return True
        else:
            print("⚠️  REDIS_URL not set (this is normal for local development)")
            return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Trakt AI List Generator - Setup Test")
    print("=" * 50)
    
    tests = [
        test_environment_variables,
        test_imports,
        test_api_connections,
        test_redis_connection
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    
    if all(results):
        print("🎉 All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Deploy to Vercel")
        print("2. Set up Redis storage in Vercel")
        print("3. Update your Trakt app redirect URI")
        print("4. Test the OAuth flow")
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
