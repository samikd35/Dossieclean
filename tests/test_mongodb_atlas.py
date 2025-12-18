import os
import pymongo
import urllib.parse
import json
from dotenv import load_dotenv
import openai
import random
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dossieclean", ".env"))

def test_mongodb_connection():
    """Test connection to MongoDB Atlas"""
    logger.info("Testing MongoDB Atlas connection...")
    
    # Get MongoDB connection parameters from environment
    username = os.environ.get("MONGO_USERNAME")
    password = os.environ.get("MONGO_PASSWORD")
    db_name = os.environ.get("DB_NAME", "Dossie")
    collection_name = os.environ.get("COLLECTION_NAME", "AAU_PDF")
    
    if not username or not password:
        logger.error("MongoDB credentials not found in environment variables")
        return False
    
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
            logger.info(f"Trying MongoDB connection with URI format...")
            client = pymongo.MongoClient(uri, **client_options)
            
            # Test connection
            client.admin.command('ping')
            logger.info("✅ Successfully connected to MongoDB Atlas")
            
            # Get database and collection
            db = client[db_name]
            collection = db[collection_name]
            
            # Check if collection exists
            if collection_name in db.list_collection_names():
                logger.info(f"✅ Collection '{collection_name}' exists")
                # Count documents
                doc_count = collection.count_documents({})
                logger.info(f"✅ Collection has {doc_count} documents")
            else:
                logger.warning(f"⚠️ Collection '{collection_name}' does not exist")
            
            return client, db, collection
        
        except Exception as e:
            logger.error(f"❌ Connection attempt failed: {str(e)}")
    
    logger.error("❌ All connection attempts failed")
    return None, None, None

def test_vector_search(client, db, collection):
    """Test MongoDB Atlas Vector Search capabilities"""
    logger.info("Testing MongoDB Atlas Vector Search...")
    
    if client is None or db is None or collection is None:
        logger.error("❌ Cannot test vector search without a valid connection")
        return False
    
    # Check if the vector search index exists
    try:
        indexes = db.command("listSearchIndexes", collection.name)
        index_found = False
        
        for index in indexes.get("cursor", {}).get("firstBatch", []):
            if index.get("name") == "AAU":
                index_found = True
                logger.info(f"✅ Vector search index 'AAU' found")
                logger.info(f"Index definition: {json.dumps(index.get('definition', {}), indent=2)}")
                break
        
        if not index_found:
            logger.warning("⚠️ Vector search index 'AAU' not found")
            logger.info("Available indexes:")
            for index in indexes.get("cursor", {}).get("firstBatch", []):
                logger.info(f"- {index.get('name')}")
            
            # Suggest creating the vector search index
            logger.info("To create a vector search index, you can use the MongoDB Atlas UI or run a command like:")
            logger.info("""
            db.runCommand({
              "createSearchIndex": "AAU_PDF",
              "name": "AAU",
              "definition": {
                "mappings": {
                  "dynamic": true,
                  "fields": {
                    "embedding": {
                      "dimensions": 1536,
                      "similarity": "cosine",
                      "type": "knnVector"
                    }
                  }
                }
              }
            })
            """)
            return False
        
        # Try a simple vector search query if we have documents
        doc_count = collection.count_documents({})
        if doc_count > 0:
            # Generate a random embedding for testing
            try:
                # Create a random embedding for testing
                random_embedding = [random.uniform(-1, 1) for _ in range(1536)]
                
                # Try the vector search
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": "AAU",
                            "path": "embedding",
                            "queryVector": random_embedding,
                            "numCandidates": 10,
                            "limit": 5
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "metadata": 1,
                            "filename": 1,
                            "score": { "$meta": "vectorSearchScore" }
                        }
                    }
                ]
                
                results = list(collection.aggregate(pipeline))
                logger.info(f"✅ Vector search test successful, found {len(results)} results")
                if results:
                    logger.info(f"First result: {json.dumps(results[0], default=str)}")
                return True
            except Exception as e:
                logger.error(f"❌ Error testing vector search: {str(e)}")
                return False
        else:
            logger.warning("⚠️ No documents in collection to test vector search")
            return True  # Return true since the index exists, even if we can't test it
    
    except Exception as e:
        logger.error(f"❌ Error checking vector search index: {str(e)}")
        return False

def test_openai_api():
    """Test OpenAI API connection"""
    logger.info("Testing OpenAI API connection...")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ OpenAI API key not found in environment variables")
        return False
    
    try:
        client = openai.OpenAI(api_key=api_key)
        models = client.models.list()
        logger.info(f"✅ Successfully connected to OpenAI API")
        logger.info(f"Available models: {', '.join([model.id for model in models.data[:5]])}...")
        return True
    except Exception as e:
        logger.error(f"❌ Error connecting to OpenAI API: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting MongoDB Atlas and Vector Search test...")
    
    # Test MongoDB connection
    client, db, collection = test_mongodb_connection()
    
    # Test vector search if connection successful
    if client is not None:
        vector_search_available = test_vector_search(client, db, collection)
        if vector_search_available:
            logger.info("✅ MongoDB Atlas Vector Search is available and working")
        else:
            logger.warning("⚠️ MongoDB Atlas Vector Search is not properly configured")
    
    # Test OpenAI API
    openai_available = test_openai_api()
    
    # Summary
    logger.info("\n=== TEST SUMMARY ===")
    logger.info(f"MongoDB Atlas Connection: {'✅ Available' if client is not None else '❌ Unavailable'}")
    if client is not None:
        logger.info(f"MongoDB Atlas Vector Search: {'✅ Available' if vector_search_available else '⚠️ Not properly configured'}")
    logger.info(f"OpenAI API: {'✅ Available' if openai_available else '❌ Unavailable'}")
    
    if client is not None and vector_search_available and openai_available:
        logger.info("✅ All services are available and properly configured")
    else:
        logger.warning("⚠️ Some services are not available or properly configured")
