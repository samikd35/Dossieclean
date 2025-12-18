import os
import pymongo
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load environment variables
load_dotenv()

# Get MongoDB credentials
username = os.environ.get("MONGO_USERNAME")
password = os.environ.get("MONGO_PASSWORD")
db_name = os.environ.get("DB_NAME")

# Properly escape special characters in username and password
escaped_username = quote_plus(username) if username else ""
escaped_password = quote_plus(password) if password else ""

# Construct the connection URI
if username and password:
    connection_uri = f"mongodb+srv://{escaped_username}:{escaped_password}@cluster0.fq7zh.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
else:
    connection_uri = "mongodb://localhost:27017/"

# Print connection info (without revealing sensitive data)
print(f"Connecting to MongoDB...")
print(f"Username: {username}")
print(f"Password: {'*' * len(password) if password else 'Not set'}")
print(f"Database: {db_name}")

try:
    # Connect to MongoDB
    client = pymongo.MongoClient(connection_uri)
    
    # Test connection
    client.admin.command('ping')
    print("\n[SUCCESS] Successfully connected to MongoDB!")
    
    # Get database info
    db = client[db_name]
    if db_name in client.list_database_names():
        print(f"Database '{db_name}' exists")
        # List collections
        collections = db.list_collection_names()
        print(f"Collections in '{db_name}':")
        for collection in collections:
            doc_count = db[collection].count_documents({})
            print(f"  - {collection}: {doc_count} documents")
    else:
        print(f"Database '{db_name}' does not exist yet (will be created on first document insertion)")
    
except Exception as e:
    print("\n[ERROR] MongoDB Connection Error:")
    print(f"Error: {e}")
    
    # Provide specific troubleshooting tips based on error
    if "@" in password and "@" in str(e):
        print("\nTroubleshooting:")
        print("- Your password contains a special character '@' which needs to be properly escaped in the connection string.")
        print("- The application should handle this automatically using quote_plus(), but in your .env file:")
        print("  1. Make sure MONGO_PASSWORD contains just the password: '0917838559@mami'")
        print("  2. Do not manually escape characters in the MONGO_URI - the code will handle this")
        
    elif "getaddrinfo failed" in str(e):
        print("\nTroubleshooting:")
        print("- Network connectivity issue or wrong hostname.")
        print("- Check your internet connection and cluster hostname.")

    elif "authentication failed" in str(e).lower():
        print("\nTroubleshooting:")
        print("- Username or password is incorrect.")
        print("- Double-check your credentials in the .env file.")
