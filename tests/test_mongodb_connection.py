import os
import pymongo
import urllib.parse
import json
from dotenv import load_dotenv
import logging
import gridfs
import random

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dossieclean", ".env"))

def connect_to_mongodb():
    """Connect to MongoDB Atlas and test basic functionality"""
    logger.info("Testing MongoDB Atlas connection...")
    
    # Get MongoDB connection parameters from environment
    username = os.environ.get("MONGO_USERNAME")
    password = os.environ.get("MONGO_PASSWORD")
    db_name = os.environ.get("DB_NAME", "Dossie")
    collection_name = os.environ.get("COLLECTION_NAME", "AAU_PDF")
    chunks_collection_name = os.environ.get("CHUNKS_COLLECTION_NAME", "AAU_PDF_CHUNKS")
    
    if not username or not password:
        logger.error("MongoDB credentials not found in environment variables")
        return None, None, None, None
    
    # Build connection URI with proper escaping
    username = urllib.parse.quote_plus(username)
    password = urllib.parse.quote_plus(password)
    
    # Standard MongoDB Atlas connection string
    uri = f"mongodb+srv://{username}:{password}@cluster0.fq7zh.mongodb.net/?retryWrites=true&w=majority"
    
    try:
        logger.info("Connecting to MongoDB Atlas...")
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=10000)
        
        # Test connection
        client.admin.command('ping')
        logger.info("✅ Successfully connected to MongoDB Atlas")
        
        # Get database and collections
        db = client[db_name]
        collection = db[collection_name]
        chunks_collection = db[chunks_collection_name]
        
        # Check if collections exist
        collections = db.list_collection_names()
        logger.info(f"Available collections: {', '.join(collections)}")
        
        if collection_name in collections:
            logger.info(f"✅ Collection '{collection_name}' exists")
            doc_count = collection.count_documents({})
            logger.info(f"✅ Collection '{collection_name}' has {doc_count} documents")
        else:
            logger.warning(f"⚠️ Collection '{collection_name}' does not exist")
            logger.info(f"Creating collection '{collection_name}'...")
            db.create_collection(collection_name)
            logger.info(f"✅ Collection '{collection_name}' created")
        
        if chunks_collection_name in collections:
            logger.info(f"✅ Collection '{chunks_collection_name}' exists")
            chunks_count = chunks_collection.count_documents({})
            logger.info(f"✅ Collection '{chunks_collection_name}' has {chunks_count} documents")
        else:
            logger.warning(f"⚠️ Collection '{chunks_collection_name}' does not exist")
            logger.info(f"Creating collection '{chunks_collection_name}'...")
            db.create_collection(chunks_collection_name)
            logger.info(f"✅ Collection '{chunks_collection_name}' created")
        
        # Test GridFS
        logger.info("Testing GridFS functionality...")
        fs = gridfs.GridFS(db)
        
        # Check if there are files in GridFS
        files_count = db.fs.files.count_documents({})
        logger.info(f"✅ GridFS has {files_count} files")
        
        # Check if we can create a simple index (not vector search)
        logger.info("Testing regular index creation...")
        try:
            collection.create_index("filename")
            logger.info("✅ Successfully created regular index on 'filename' field")
        except Exception as e:
            logger.error(f"❌ Error creating regular index: {str(e)}")
        
        # Check if we can store and retrieve a document with an embedding
        logger.info("Testing document storage with embedding field...")
        try:
            # Create a test document with a random embedding
            test_doc = {
                "filename": "test_document.pdf",
                "metadata": {
                    "title": "Test Document",
                    "authors": ["Test, A."],
                    "year": "2025"
                },
                "embedding": [random.uniform(-1, 1) for _ in range(1536)]
            }
            
            # Insert the document
            test_id = collection.insert_one(test_doc).inserted_id
            logger.info(f"✅ Successfully inserted test document with ID: {test_id}")
            
            # Retrieve the document
            retrieved_doc = collection.find_one({"_id": test_id})
            if retrieved_doc:
                logger.info("✅ Successfully retrieved test document with embedding")
                # Clean up - remove the test document
                collection.delete_one({"_id": test_id})
                logger.info("✅ Successfully cleaned up test document")
            else:
                logger.error("❌ Failed to retrieve test document")
        except Exception as e:
            logger.error(f"❌ Error testing document storage: {str(e)}")
        
        return client, db, collection, chunks_collection
    
    except Exception as e:
        logger.error(f"❌ Error connecting to MongoDB Atlas: {str(e)}")
        return None, None, None, None

def print_atlas_search_instructions():
    """Print instructions for enabling Atlas Search"""
    logger.info("\n=== ATLAS SEARCH SETUP INSTRUCTIONS ===")
    logger.info("To enable Atlas Search in MongoDB Atlas, follow these steps:")
    logger.info("1. Log in to your MongoDB Atlas account at https://cloud.mongodb.com")
    logger.info("2. Navigate to your cluster")
    logger.info("3. Click on the 'Search' tab")
    logger.info("4. Click 'Create Search Index'")
    logger.info("5. Choose 'Visual Editor' and select your database and collection")
    logger.info("6. Name your index 'AAU' (or any name you prefer)")
    logger.info("7. In the index definition, add a field mapping for 'embedding':")
    logger.info("   - Field name: embedding")
    logger.info("   - Type: knnVector")
    logger.info("   - Dimensions: 1536")
    logger.info("   - Similarity: cosine")
    logger.info("8. Click 'Create Index'")
    logger.info("9. Repeat the process for your chunks collection if needed")
    logger.info("\nAlternatively, you can create the index using the MongoDB Atlas API or CLI")
    logger.info("For more information, visit: https://www.mongodb.com/docs/atlas/atlas-search/")

if __name__ == "__main__":
    logger.info("Starting MongoDB Atlas connection test...")
    
    # Connect to MongoDB and test basic functionality
    client, db, collection, chunks_collection = connect_to_mongodb()
    
    if client is not None:
        logger.info("\n=== TEST SUMMARY ===")
        logger.info("✅ MongoDB Atlas connection is working")
        logger.info("✅ Basic database operations are working")
        logger.info("⚠️ Atlas Search needs to be enabled manually in the MongoDB Atlas console")
        
        # Print instructions for enabling Atlas Search
        print_atlas_search_instructions()
    else:
        logger.error("❌ MongoDB Atlas connection failed")
