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
    """Connect to MongoDB Atlas"""
    logger.info("Connecting to MongoDB Atlas...")
    
    # Get MongoDB connection parameters from environment
    username = os.environ.get("MONGO_USERNAME")
    password = os.environ.get("MONGO_PASSWORD")
    db_name = os.environ.get("DB_NAME", "Dossie")
    
    if not username or not password:
        logger.error("MongoDB credentials not found in environment variables")
        return None, None
    
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
        
        # Get database
        db = client[db_name]
        
        return client, db
    
    except Exception as e:
        logger.error(f"❌ Error connecting to MongoDB Atlas: {str(e)}")
        return None, None

def verify_collections(db):
    """Verify that the required collections exist"""
    logger.info("Verifying collections...")
    
    # Collection names
    main_collection_name = "AAU_PDF"
    
    # Check if collections exist
    collections = db.list_collection_names()
    logger.info(f"Available collections: {', '.join(collections)}")
    
    # Check main collection
    if main_collection_name in collections:
        logger.info(f"✅ Collection '{main_collection_name}' exists")
        doc_count = db[main_collection_name].count_documents({})
        logger.info(f"✅ Collection '{main_collection_name}' has {doc_count} documents")
    else:
        logger.warning(f"⚠️ Collection '{main_collection_name}' does not exist")
        logger.info(f"Creating collection '{main_collection_name}'...")
        db.create_collection(main_collection_name)
        logger.info(f"✅ Collection '{main_collection_name}' created")
    
    # Check GridFS
    logger.info("Checking GridFS...")
    fs = gridfs.GridFS(db)
    files_count = db.fs.files.count_documents({})
    logger.info(f"✅ GridFS has {files_count} files")
    
    return db[main_collection_name]

def check_vector_search_index(db, collection_name, index_name="AAU_Vector"):
    """Check if a vector search index exists for the collection"""
    logger.info(f"Checking if vector search index '{index_name}' exists for collection '{collection_name}'...")
    
    try:
        # List search indexes
        indexes = db.command("listSearchIndexes", collection_name)
        
        # Check if our index exists
        for index in indexes.get("cursor", {}).get("firstBatch", []):
            if index.get("name") == index_name:
                logger.info(f"✅ Vector search index '{index_name}' exists for collection '{collection_name}'")
                logger.info(f"Index definition: {json.dumps(index.get('definition', {}), indent=2)}")
                return True
        
        logger.warning(f"⚠️ Vector search index '{index_name}' does not exist for collection '{collection_name}'")
        return False
    
    except Exception as e:
        if "command not found" in str(e):
            logger.warning(f"⚠️ Atlas Search is not enabled on this cluster")
            logger.info("You need to enable Atlas Search in the MongoDB Atlas console")
            return False
        else:
            logger.error(f"❌ Error checking vector search index: {str(e)}")
            return False

def print_atlas_search_instructions():
    """Print instructions for enabling Atlas Search"""
    logger.info("\n=== ATLAS SEARCH SETUP INSTRUCTIONS ===")
    logger.info("To enable Atlas Search in MongoDB Atlas, follow these steps:")
    logger.info("1. Log in to your MongoDB Atlas account at https://cloud.mongodb.com")
    logger.info("2. Navigate to your cluster")
    logger.info("3. Click on the 'Search' tab")
    logger.info("4. Click 'Create Search Index'")
    logger.info("5. Choose 'Visual Editor' and select your database (Dossie) and collection (AAU_PDF)")
    logger.info("6. Name your index 'AAU_Vector'")
    logger.info("7. In the index definition, add a field mapping for 'embedding':")
    logger.info("   - Field name: embedding")
    logger.info("   - Type: knnVector")
    logger.info("   - Dimensions: 1536")
    logger.info("   - Similarity: cosine")
    logger.info("8. Click 'Create Index'")
    logger.info("\nFor more information, visit: https://www.mongodb.com/docs/atlas/atlas-search/")

def test_document_with_embedding(collection):
    """Test storing and retrieving a document with an embedding"""
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
            return True
        else:
            logger.error("❌ Failed to retrieve test document")
            return False
    except Exception as e:
        logger.error(f"❌ Error testing document storage: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting MongoDB Atlas verification...")
    
    # Connect to MongoDB
    client, db = connect_to_mongodb()
    
    if client is not None and db is not None:
        # Verify collections
        collection = verify_collections(db)
        
        # Check vector search index
        vector_search_available = check_vector_search_index(db, "AAU_PDF", "AAU_Vector")
        
        # Test document storage with embedding
        if collection is not None:
            document_storage_working = test_document_with_embedding(collection)
        else:
            document_storage_working = False
        
        # Print summary
        logger.info("\n=== VERIFICATION SUMMARY ===")
        logger.info(f"MongoDB Atlas Connection: ✅ Available")
        logger.info(f"Collection 'AAU_PDF': ✅ Available")
        logger.info(f"GridFS: ✅ Available")
        logger.info(f"Document Storage with Embedding: {'✅ Working' if document_storage_working else '❌ Not Working'}")
        logger.info(f"Vector Search Index 'AAU_Vector': {'✅ Available' if vector_search_available else '⚠️ Not Available'}")
        
        # Print instructions if vector search is not available
        if not vector_search_available:
            print_atlas_search_instructions()
    else:
        logger.error("❌ MongoDB Atlas connection failed")
