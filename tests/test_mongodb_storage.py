import os
import gridfs
import pymongo
from pymongo.mongo_client import MongoClient
from dotenv import load_dotenv
import pprint
import urllib.parse

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_USERNAME = os.environ.get("MONGO_USERNAME")
MONGO_PASSWORD = os.environ.get("MONGO_PASSWORD")
DB_NAME = os.environ.get("DB_NAME", "dossieclean")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "documents")

def test_mongodb_storage():
    """Test the MongoDB storage by listing all documents and files in GridFS"""
    print("Testing MongoDB storage...")
    
    # Create MongoDB connection URI
    if MONGO_USERNAME and MONGO_PASSWORD:
        username = urllib.parse.quote_plus(MONGO_USERNAME)
        password = urllib.parse.quote_plus(MONGO_PASSWORD)
        # Use the same connection string as in app.py
        uri = f"mongodb+srv://{username}:{password}@cluster0.fq7zh.mongodb.net/?retryWrites=true&w=majority"
        print(f"Using database: {DB_NAME}, collection: {COLLECTION_NAME}")
    else:
        print("MongoDB credentials not found in environment variables")
        return False
    
    try:
        # Connect to MongoDB with increased timeout
        print("Connecting to MongoDB Atlas...")
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        
        # Verify connection
        client.admin.command('ping')
        print("Connected to MongoDB Atlas successfully!")
        
        # Access database and collection
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        fs = gridfs.GridFS(db)
        
        # Count documents in the collection
        doc_count = collection.count_documents({})
        print(f"\nFound {doc_count} documents in the collection '{COLLECTION_NAME}'")
        
        # List documents
        if doc_count > 0:
            print("\nDocument Metadata (latest 5):")
            for doc in collection.find().sort('upload_date', -1).limit(5):
                print("\n---Document---")
                # Print document except for potentially large fields
                display_doc = {k: v for k, v in doc.items() if k not in ['full_text', 'vector']}
                
                # Add file information if available
                if 'file_id' in doc:
                    file_id = doc['file_id']
                    # Check if file exists in GridFS
                    if fs.exists(file_id):
                        grid_file = fs.get(file_id)
                        display_doc['gridfs_file_size'] = grid_file.length
                        display_doc['gridfs_file_name'] = grid_file.filename
                        display_doc['gridfs_content_type'] = grid_file.content_type if hasattr(grid_file, 'content_type') else 'Not specified'
                    else:
                        display_doc['gridfs_file_status'] = "Referenced file not found in GridFS"
                
                # Pretty print the document
                pprint.pprint(display_doc)
        
        # Count GridFS files
        files_count = db.fs.files.count_documents({})
        print(f"\nFound {files_count} files stored in GridFS")
        
        # List GridFS files
        if files_count > 0:
            print("\nGridFS Files (latest 5):")
            for file_info in db.fs.files.find().sort('uploadDate', -1).limit(5):
                print("\n---File---")
                # Print file info
                display_file = {
                    'filename': file_info.get('filename'),
                    'length': file_info.get('length'),
                    'uploadDate': file_info.get('uploadDate'),
                    '_id': file_info.get('_id')
                }
                pprint.pprint(display_file)
                
                # Check if this file is referenced by any document
                referencing_docs = collection.count_documents({'file_id': file_info.get('_id')})
                print(f"This file is referenced by {referencing_docs} documents")
        
        return True
    
    except Exception as e:
        print(f"Error testing MongoDB storage: {e}")
        return False

if __name__ == "__main__":
    test_mongodb_storage()
