import pymongo
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load environment variables
load_dotenv()

# Get MongoDB credentials
username = os.environ.get("MONGO_USERNAME")
password = os.environ.get("MONGO_PASSWORD")

# Test local connection first
try:
    print("Attempting to connect to local MongoDB instance...")
    local_client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    local_client.admin.command('ping')
    print("[SUCCESS] Connected to local MongoDB instance")
except Exception as e:
    print(f"[ERROR] Could not connect to local MongoDB: {e}")
    print("Note: This is expected if you don't have MongoDB installed locally.")

# Try a different format for Atlas connection
if username and password:
    # Properly escape username and password
    escaped_username = quote_plus(username)
    escaped_password = quote_plus(password)
    
    print("\nAttempting to connect to MongoDB Atlas using alternative format...")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    
    # Try different Atlas connection formats
    connection_uris = [
        f"mongodb+srv://{escaped_username}:{escaped_password}@cluster0.fq7zh.mongodb.net/?retryWrites=true&w=majority",
        f"mongodb+srv://{escaped_username}:{escaped_password}@cluster0.fq7zh.mongodb.net/Dossie?retryWrites=true&w=majority"
    ]
    
    for i, uri in enumerate(connection_uris):
        try:
            print(f"\nTrying connection format #{i+1}...")
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=10000)
            client.admin.command('ping')
            print(f"[SUCCESS] Connected to MongoDB Atlas using format #{i+1}")
            break
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
else:
    print("\nSkipping Atlas connection test - username or password not provided")

print("\nTroubleshooting Tips:")
print("1. Check your internet connection")
print("2. Verify the cluster name (cluster0.fq7zh.mongodb.net) is correct")
print("3. Ensure your IP address is whitelisted in MongoDB Atlas")
print("4. Try creating a new database user in MongoDB Atlas with a simple password (no special characters)")
print("5. If you're behind a corporate firewall, try connecting from a different network")
