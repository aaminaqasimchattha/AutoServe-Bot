#!/usr/bin/env python3
"""
Script to verify embeddings in Pinecone vector database.
Run this after uploading files to check if embeddings were stored.
"""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def verify_pinecone_embeddings():
    """Check Pinecone index for stored embeddings."""
    
    logger.info("=" * 60)
    logger.info("PINECONE EMBEDDINGS VERIFICATION")
    logger.info("=" * 60)
    
    try:
        from pinecone import Pinecone
    except ImportError:
        logger.error("✗ Pinecone SDK not installed")
        logger.info("Install with: uv pip install pinecone-client")
        return False
    
    api_key = (os.getenv("PINECONE_API_KEY") or os.getenv("PINECONE_KEY") or "").strip()
    if not api_key:
        logger.error("✗ Pinecone API key not found")
        return False
    
    try:
        logger.info("\n1. Connecting to Pinecone...")
        pc = Pinecone(api_key=api_key)
        logger.info("✓ Connected to Pinecone")
        
        index_name = os.getenv("PINECONE_INDEX_NAME", "autoserve")
        logger.info(f"\n2. Accessing index: {index_name}")
        index = pc.Index(name=index_name)
        logger.info(f"✓ Connected to index '{index_name}'")
        
        # Get index statistics
        logger.info("\n3. Fetching index statistics...")
        stats = index.describe_index_stats()
        logger.info(f"✓ Index stats retrieved")
        
        # Display statistics
        logger.info("\n" + "=" * 60)
        logger.info("INDEX STATISTICS")
        logger.info("=" * 60)
        
        total_vectors = stats.total_vector_count
        logger.info(f"Total vectors in index: {total_vectors:,}")
        
        # Show namespace information
        if hasattr(stats, 'namespaces') and stats.namespaces:
            logger.info("\nVectors by namespace:")
            for ns, ns_stats in stats.namespaces.items():
                count = ns_stats.vector_count if hasattr(ns_stats, 'vector_count') else ns_stats.get('vector_count', 0)
                logger.info(f"  - {ns or 'default'}: {count:,} vectors")
        
        # Check upload index for recent uploads
        upload_index_file = Path(__file__).parent / "uploads" / "upload_index.json"
        if upload_index_file.exists():
            logger.info("\n4. Recent file uploads:")
            uploads = json.loads(upload_index_file.read_text())
            
            if uploads:
                # Show last 5 uploads
                for upload in uploads[-5:]:
                    filename = upload.get('filename', 'unknown')
                    size = upload.get('size', 0)
                    timestamp = upload.get('saved_at', 'unknown')
                    
                    # Parse timestamp
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        time_str = timestamp
                    
                    logger.info(f"  - {filename} ({size:,} bytes) - {time_str}")
            else:
                logger.info("  No uploads recorded yet")
        
        # Query a sample vector to verify data is there
        if total_vectors > 0:
            logger.info("\n5. Verifying data integrity...")
            try:
                # Query with a random vector to see sample metadata
                results = index.query(
                    vector=[0.0] * 384,  # All-zero vector for testing
                    top_k=1,
                    include_metadata=True
                )
                
                if results and results.matches:
                    match = results.matches[0]
                    metadata = match.get('metadata', {})
                    logger.info("✓ Sample record retrieved:")
                    logger.info(f"  - ID: {match.get('id', 'N/A')[:50]}...")
                    logger.info(f"  - Score: {match.get('score', 'N/A')}")
                    logger.info(f"  - Source: {metadata.get('source_name', 'N/A')}")
                    if 'text' in metadata:
                        text_preview = metadata['text'][:100]
                        logger.info(f"  - Text: {text_preview}...")
            except Exception as e:
                logger.warning(f"Could not retrieve sample: {str(e)}")
        
        logger.info("\n" + "=" * 60)
        if total_vectors > 0:
            logger.info(f"✓ SUCCESS: {total_vectors:,} vectors found in Pinecone!")
            logger.info("Your embeddings have been successfully stored.")
        else:
            logger.warning("⚠ No vectors found in index yet")
            logger.info("Try uploading a file first: POST /api/upload")
        
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"✗ Error accessing Pinecone: {str(e)}")
        logger.info("\nTroubleshooting:")
        logger.info("1. Verify PINECONE_KEY is set in .env")
        logger.info("2. Check your internet connection")
        logger.info("3. Ensure index 'autoserve' exists in your Pinecone account")
        return False


if __name__ == "__main__":
    import sys
    success = verify_pinecone_embeddings()
    sys.exit(0 if success else 1)
