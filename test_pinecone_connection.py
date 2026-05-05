#!/usr/bin/env python3
"""
Diagnostic script to test Pinecone connectivity and SSL certificate handling.
Run this to troubleshoot Pinecone connection issues.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

def test_dns_resolution():
    """Test if Pinecone host can be resolved."""
    logger.info("=" * 60)
    logger.info("1. Testing DNS Resolution")
    logger.info("=" * 60)
    
    try:
        import socket
        hostname = "autoserve-d6ukgp8.svc.aped-4627-b74a.pinecone.io"
        logger.info(f"Attempting to resolve: {hostname}")
        result = socket.getaddrinfo(hostname, 443)
        logger.info(f"✓ DNS Resolution successful: {result[0][4]}")
        return True
    except socket.gaierror as e:
        logger.error(f"✗ DNS Resolution failed: {str(e)}")
        logger.info("This might be due to:")
        logger.info("  - Corporate proxy blocking DNS")
        logger.info("  - Network connectivity issues")
        logger.info("  - Incorrect Pinecone endpoint")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error during DNS test: {str(e)}")
        return False


def test_ssl_connection():
    """Test SSL certificate verification."""
    logger.info("\n" + "=" * 60)
    logger.info("2. Testing SSL Certificate Verification")
    logger.info("=" * 60)
    
    try:
        import ssl
        import socket
        
        hostname = "autoserve-d6ukgp8.svc.aped-4627-b74a.pinecone.io"
        port = 443
        
        logger.info(f"Attempting SSL connection to {hostname}:{port}")
        
        context = ssl.create_default_context()
        try:
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    logger.info(f"✓ SSL connection successful")
                    logger.info(f"  Certificate: {ssock.getpeercert()}")
                    return True
        except ssl.SSLError as ssl_err:
            logger.error(f"✗ SSL Certificate Error: {str(ssl_err)}")
            logger.info("This is expected with corporate proxy. Will use verify=False.")
            return False
            
    except Exception as e:
        logger.error(f"✗ Unexpected error during SSL test: {str(e)}")
        return False


def test_pinecone_api_key():
    """Test if Pinecone API key is configured."""
    logger.info("\n" + "=" * 60)
    logger.info("3. Testing Pinecone API Key Configuration")
    logger.info("=" * 60)
    
    api_key = (os.getenv("PINECONE_API_KEY") or os.getenv("PINECONE_KEY") or "").strip()
    
    if not api_key:
        logger.error("✗ No Pinecone API key found in environment")
        logger.info("Set PINECONE_API_KEY or PINECONE_KEY in .env file")
        return False
    
    logger.info(f"✓ API key found (length: {len(api_key)} chars)")
    logger.info(f"  First 10 chars: {api_key[:10]}...")
    return True


def test_pinecone_initialization():
    """Test Pinecone client initialization with SSL bypass."""
    logger.info("\n" + "=" * 60)
    logger.info("4. Testing Pinecone Client Initialization")
    logger.info("=" * 60)
    
    try:
        from pinecone import Pinecone
    except ImportError:
        logger.error("✗ Pinecone SDK not installed")
        logger.info("Install with: pip install pinecone-client")
        return False
    
    api_key = (os.getenv("PINECONE_API_KEY") or os.getenv("PINECONE_KEY") or "").strip()
    if not api_key:
        logger.error("✗ API key not available")
        return False
    
    # Test 1: Standard initialization
    logger.info("Attempting standard initialization...")
    try:
        pc = Pinecone(api_key=api_key)
        logger.info("✓ Standard initialization successful")
        return True
    except Exception as e:
        logger.warning(f"✗ Standard initialization failed: {str(e)[:100]}")
    
    # Test 2: With httpx client verify=False
    logger.info("Attempting initialization with SSL verification disabled...")
    try:
        import httpx
        http_client = httpx.Client(verify=False)
        pc = Pinecone(api_key=api_key, http_client=http_client)
        logger.info("✓ Initialization with verify=False successful")
        
        # Try to access the index
        try:
            index_name = os.getenv("PINECONE_INDEX_NAME", "autoserve")
            index = pc.Index(name=index_name)
            logger.info(f"✓ Successfully connected to index '{index_name}'")
            return True
        except Exception as idx_err:
            logger.warning(f"✗ Could not access index: {str(idx_err)[:100]}")
            return False
            
    except Exception as e:
        logger.error(f"✗ SSL verification bypass failed: {str(e)[:100]}")
        return False


def main():
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 15 + "PINECONE CONNECTIVITY TEST" + " " * 17 + "║")
    logger.info("╚" + "=" * 58 + "╝")
    
    results = {}
    results['DNS'] = test_dns_resolution()
    results['SSL'] = test_ssl_connection()
    results['API Key'] = test_pinecone_api_key()
    results['Pinecone Init'] = test_pinecone_initialization()
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{test_name:20} {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n✓ All tests passed! Pinecone should work correctly.")
        sys.exit(0)
    else:
        logger.info("\n✗ Some tests failed. Check the error messages above.")
        logger.info("\nCommon fixes:")
        logger.info("1. Verify PINECONE_API_KEY is set correctly in .env")
        logger.info("2. Check your internet connection")
        logger.info("3. If behind corporate proxy, verify proxy settings")
        logger.info("4. Try running with: python test_pinecone_connection.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
