#!/usr/bin/env python3
"""
Test script to verify installation and basic functionality
"""

import os

def test_imports():
    """Test that all required modules can be imported."""
    try:
        import requests
        print("✓ requests imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import requests: {e}")
        return False
    
    try:
        import xml.etree.ElementTree as ET
        print("✓ xml.etree.ElementTree imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import xml.etree.ElementTree: {e}")
        return False
    
    try:
        from bs4 import BeautifulSoup
        print("✓ beautifulsoup4 imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import beautifulsoup4: {e}")
        return False
    
    try:
        import openai
        print("✓ openai imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import openai: {e}")
        return False
    
    try:
        from urllib.parse import urljoin, urlparse
        print("✓ urllib.parse imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import urllib.parse: {e}")
        return False
    
    return True

def test_scraper_import():
    """Test that the ShopifyScraper class can be imported."""
    try:
        from ask import ShopifyScraper
        print("✓ ShopifyScraper imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import ShopifyScraper: {e}")
        return False

def test_api_key():
    """Test that the API key is properly formatted."""
    api_key = os.getenv('OPENAI_API_KEY')
    
    if api_key and api_key.startswith("sk-") and len(api_key) > 20:
        print("✓ API key format looks correct")
        return True
    else:
        print("✗ API key not found or format appears incorrect")
        print("   Set OPENAI_API_KEY environment variable or enter when prompted")
        return False

def test_openai_api():
    """Test that the OpenAI API connection is successful."""
    try:
        openai_client = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY') or input("Please enter your OpenAI API key: ")
        )
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello, this is a test."}],
            max_tokens=10
        )
        print("✅ OpenAI API connection successful")
    except Exception as e:
        print(f"❌ OpenAI API connection failed: {e}")
        print("   Make sure you have a valid OpenAI API key set in OPENAI_API_KEY environment variable")

def main():
    """Run all tests."""
    print("Testing Shopify Scraper Installation...")
    print("=" * 40)
    
    all_tests_passed = True
    
    # Test imports
    if not test_imports():
        all_tests_passed = False
    
    print()
    
    # Test scraper import
    if not test_scraper_import():
        all_tests_passed = False
    
    print()
    
    # Test API key
    if not test_api_key():
        all_tests_passed = False
    
    print()
    
    # Test OpenAI API
    if not test_openai_api():
        all_tests_passed = False
    
    print()
    print("=" * 40)
    
    if all_tests_passed:
        print("✓ All tests passed! The scraper is ready to use.")
        print("\nTo use the scraper, run:")
        print("python ask.py <base_url>")
        print("\nExample:")
        print("python ask.py https://example-shop.com")
    else:
        print("✗ Some tests failed. Please check the installation.")
        print("\nTo install dependencies, run:")
        print("pip install -r requirements.txt")

if __name__ == "__main__":
    main() 