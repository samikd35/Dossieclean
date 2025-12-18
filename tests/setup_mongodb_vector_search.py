import os
import pymongo
import urllib.parse
import json
from dotenv import load_dotenv
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dossieclean", ".env"))

def connect_to_mongodb():
    """Connect to MongoDB Atlas"""
    logger.info("Connecting to MongoDB Atlas...")
    
    # Get MongoDB connection parameters from environment
    username = os.environ.get("MONGO_USERNAME")
    password = os.environ.get("MONGO_PASSWORD")
    db_name = os.environ.get("DB_NAME", "Dossie")
    collection_name = os.environ.get("COLLECTION_NAME", "AAU_PDF")
    
    if not username or not password:
        logger.error("MongoDB credentials not found in environment variables")
        return None, None, None
    
    # Build connection URI with proper escaping
    username = urllib.parse.quote_plus(username)
    password = urllib.parse.quote_plus(password)
    
    # Try different connection string formats
    connection_uris = [
        # Standard format with cluster0.fq7zh
        f"mongodb+srv://{username}:{password}@cluster0.fq7zh.mongodb.net/?retryWrites=true&w=majority&tls=true&appName=Cluster0",
        # Try without tls and appName
        f"mongodb+srv://{username}:{password}@cluster0.fq7zh.mongodb.net/?retryWrites=true&w=majority",
        # Try with direct connection to avoid DNS issues
        f"mongodb://{username}:{password}@ac-fwkqsrm-shard-00-00.fq7zh.mongodb.net:27017,ac-fwkqsrm-shard-00-01.fq7zh.mongodb.net:27017,ac-fwkqsrm-shard-00-02.fq7zh.mongodb.net:27017/?ssl=true&replicaSet=atlas-qdl0dj-shard-0&authSource=admin&retryWrites=true&w=majority"
    ]
    
    # Client options
    client_options = {
        "serverSelectionTimeoutMS": 10000,
        "connectTimeoutMS": 10000,
        "socketTimeoutMS": 20000,
        "retryWrites": True,
        "retryReads": True
    }
    
    # Try each connection URI format
    for uri in connection_uris:
        try:
            logger.info(f"Trying MongoDB connection...")
            client = pymongo.MongoClient(uri, **client_options)
            
            # Test connection
            client.admin.command('ping')
            logger.info("✅ Successfully connected to MongoDB Atlas")
            
            # Get database and collection
            db = client[db_name]
            collection = db[collection_name]
            chunks_collection = db.get_collection(os.environ.get("CHUNKS_COLLECTION_NAME", "AAU_PDF_CHUNKS"))
            
            return client, db, collection, chunks_collection
        
        except Exception as e:
            logger.error(f"❌ Connection attempt failed: {str(e)}")
    
    logger.error("❌ All connection attempts failed")
    return None, None, None, None

def create_vector_search_index(db, collection_name, index_name="AAU"):
    """Create a vector search index for the collection"""
    logger.info(f"Creating vector search index '{index_name}' for collection '{collection_name}'...")
    
    try:
        # Define the vector search index
        index_definition = {
            "mappings": {
                "dynamic": True,
                "fields": {
                    "embedding": {
                        "dimensions": 1536,
                        "similarity": "cosine",
                        "type": "knnVector"
                    }
                }
            }
        }
        
        # Create the index
        db.command({
            "createSearchIndex": collection_name,
            "name": index_name,
            "definition": index_definition
        })
        
        logger.info(f"✅ Successfully created vector search index '{index_name}' for collection '{collection_name}'")
        return True
    
    except Exception as e:
        logger.error(f"❌ Error creating vector search index: {str(e)}")
        return False

def check_vector_search_index(db, collection_name, index_name="AAU"):
    """Check if a vector search index exists for the collection"""
    logger.info(f"Checking if vector search index '{index_name}' exists for collection '{collection_name}'...")
    
    try:
        # List search indexes
        indexes = db.command("listSearchIndexes", collection_name)
        
        # Check if our index exists
        for index in indexes.get("cursor", {}).get("firstBatch", []):
            if index.get("name") == index_name:
                logger.info(f"✅ Vector search index '{index_name}' already exists")
                return True
        
        logger.info(f"⚠️ Vector search index '{index_name}' does not exist")
        return False
    
    except Exception as e:
        logger.error(f"❌ Error checking vector search index: {str(e)}")
        return False

def setup_vector_search():
    """Set up vector search indexes for both collections"""
    client, db, collection, chunks_collection = connect_to_mongodb()
    
    if db is None:
        logger.error("❌ Cannot set up vector search without a valid connection")
        return False
    
    # Check and create vector search index for main collection
    collection_name = os.environ.get("COLLECTION_NAME", "AAU_PDF")
    if not check_vector_search_index(db, collection_name):
        create_vector_search_index(db, collection_name)
    
    # Check and create vector search index for chunks collection
    chunks_collection_name = os.environ.get("CHUNKS_COLLECTION_NAME", "AAU_PDF_CHUNKS")
    if not check_vector_search_index(db, chunks_collection_name):
        create_vector_search_index(db, chunks_collection_name)
    
    return True

if __name__ == "__main__":
    logger.info("Setting up MongoDB Atlas Vector Search...")
    
    # Set up vector search
    success = setup_vector_search()
    
    if success:
        logger.info("✅ MongoDB Atlas Vector Search setup complete")
    else:
        logger.error("❌ MongoDB Atlas Vector Search setup failed")
