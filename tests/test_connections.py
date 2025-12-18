import os
import pymongo
import requests
import json
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load environment variables
load_dotenv()

def test_mongodb_connection():
    """Test MongoDB Atlas connection"""
    print("\n=== Testing MongoDB Atlas Connection ===")
    
    # Get MongoDB credentials
    username = os.environ.get("MONGO_USERNAME")
    password = os.environ.get("MONGO_PASSWORD")
    db_name = os.environ.get("DB_NAME", "Dossie")
    
    if not username or not password:
        print("MongoDB credentials not found in .env file")
        return False
    
    # Properly escape special characters in username and password
    escaped_username = quote_plus(username)
    escaped_password = quote_plus(password)
    
    # Construct connection string
    connection_uri = f"mongodb+srv://{escaped_username}:{escaped_password}@cluster0.fq7zh.mongodb.net/?retryWrites=true&w=majority"
    
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    print(f"Database: {db_name}")
    
    try:
        # Create connection
        client = pymongo.MongoClient(connection_uri, serverSelectionTimeoutMS=5000)
        
        # Test connection with ping
        client.admin.command('ping')
        print("[SUCCESS] MongoDB Atlas connection successful!")
        
        # Check database and collections
        db = client[db_name]
        print(f"[SUCCESS] Connected to database: {db_name}")
        
        # List collections
        collections = db.list_collection_names()
        if collections:
            print(f"[SUCCESS] Found {len(collections)} collections:")
            for collection in collections:
                print(f"  - {collection}")
        else:
            print("[SUCCESS] No collections found (database may be empty)")
        
        return True
    except Exception as e:
        print(f"[ERROR] MongoDB Atlas connection failed: {e}")
        return False

def test_qdrant_connection():
    """Test Qdrant connection"""
    print("\n=== Testing Qdrant Connection ===")
    
    # Get Qdrant credentials
    api_key = os.environ.get("QDRANT_API_KEY")
    api_url = os.environ.get("QDRANT_URL")
    
    if not api_key or not api_url:
        print("Qdrant credentials not found in .env file")
        return False
    
    print(f"API URL: {api_url}")
    print(f"API Key: {api_key[:5]}...{api_key[-5:]}")
    
    # Set up headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        # Test connection by listing collections
        response = requests.get(f"{api_url}/collections", headers=headers)
        
        if response.status_code == 200:
            collections = response.json()
            print("[SUCCESS] Qdrant connection successful!")
            
            if "result" in collections and "collections" in collections["result"]:
                qdrant_collections = collections["result"]["collections"]
                if qdrant_collections:
                    print(f"[SUCCESS] Found {len(qdrant_collections)} collections:")
                    for collection in qdrant_collections:
                        print(f"  - {collection['name']}")
                else:
                    print("[SUCCESS] No collections found (Qdrant may be empty)")
            else:
                print("[SUCCESS] No collections found (Qdrant may be empty)")
                
            # Check for DossieScholar collection
            dossie_response = requests.get(f"{api_url}/collections/DossieScholar", headers=headers)
            if dossie_response.status_code == 200:
                print("[SUCCESS] DossieScholar collection exists")
            elif dossie_response.status_code == 404:
                print("[INFO] DossieScholar collection does not exist yet")
                
                # Create DossieScholar collection
                create_collection = input("Would you like to create the DossieScholar collection? (y/n): ")
                if create_collection.lower() == "y":
                    create_payload = {
                        "vectors": {
                            "size": 1536,
                            "distance": "Cosine"
                        }
                    }
                    create_response = requests.put(
                        f"{api_url}/collections/DossieScholar", 
                        headers=headers, 
                        json=create_payload
                    )
                    if create_response.status_code == 200:
                        print("[SUCCESS] Successfully created DossieScholar collection")
                    else:
                        print(f"[ERROR] Failed to create collection: {create_response.status_code} - {create_response.text}")
            else:
                print(f"[ERROR] Error checking DossieScholar collection: {dossie_response.status_code} - {dossie_response.text}")
                
            return True
        else:
            print(f"[ERROR] Qdrant connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Qdrant connection failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing connections to MongoDB Atlas and Qdrant...")
    
    # Test MongoDB Atlas connection
    mongo_success = test_mongodb_connection()
    
    # Test Qdrant connection
    qdrant_success = test_qdrant_connection()
    
    # Summary
    print("\n=== Connection Test Summary ===")
    print(f"MongoDB Atlas: {'[SUCCESS] Connected' if mongo_success else '[ERROR] Failed'}")
    print(f"Qdrant: {'[SUCCESS] Connected' if qdrant_success else '[ERROR] Failed'}")
    
    if mongo_success and qdrant_success:
        print("\n[SUCCESS] All connections successful! Your application should work correctly.")
    elif not mongo_success and not qdrant_success:
        print("\n[ERROR] Both connections failed. Please check your credentials and network.")
    else:
        print("\n[WARNING] Some connections failed. Please check the specific errors above.")
