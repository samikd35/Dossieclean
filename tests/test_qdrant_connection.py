import os
import requests
import json
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Qdrant configuration
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")
QDRANT_URL = os.environ.get("QDRANT_URL")

def test_qdrant_connection():
    """Test the connection to Qdrant and perform basic operations"""
    print(f"Testing connection to Qdrant at {QDRANT_URL}")
    
    headers = {
        "Authorization": f"Bearer {QDRANT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Step 1: List all collections
    print("\nStep 1: Listing collections")
    response = requests.get(
        f"{QDRANT_URL}/collections",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Failed to list collections: {response.text}")
        return
    
    print(f"Collections response: {response.text}")
    
    # Step 2: Create test collection if it doesn't exist
    print("\nStep 2: Creating test collection")
    collection_name = "qdrant_test"
    
    # Check if collection exists
    response = requests.get(
        f"{QDRANT_URL}/collections/{collection_name}",
        headers=headers
    )
    
    if response.status_code == 200:
        print(f"Collection '{collection_name}' already exists")
    else:
        # Create collection
        collection_config = {
            "name": collection_name,
            "vectors": {
                "size": 4,  # Small size for test
                "distance": "Cosine"
            }
        }
        
        response = requests.put(
            f"{QDRANT_URL}/collections/{collection_name}",
            headers=headers,
            json=collection_config
        )
        
        if response.status_code != 200:
            print(f"Failed to create collection: {response.text}")
            return
        
        print(f"Collection '{collection_name}' created successfully")
    
    # Step 3: Insert a test point
    print("\nStep 3: Inserting test point")
    test_id = random.randint(1, 1000000)
    test_point = {
        "ids": [test_id],
        "vectors": [[0.1, 0.2, 0.3, 0.4]],
        "payloads": [{"test": "value", "source": "dossieclean_test"}]
    }
    
    response = requests.post(
        f"{QDRANT_URL}/collections/{collection_name}/points",
        headers=headers,
        json=test_point
    )
    
    if response.status_code != 200:
        print(f"Failed to insert test point: {response.text}")
        return
    
    print(f"Test point inserted successfully: {response.text}")
    
    # Step 4: Retrieve the test point
    print("\nStep 4: Retrieving test point")
    response = requests.get(
        f"{QDRANT_URL}/collections/{collection_name}/points/{test_id}",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Failed to retrieve test point: {response.text}")
        return
    
    print(f"Test point retrieved successfully: {json.dumps(response.json(), indent=2)}")
    
    # Step 5: Search for points
    print("\nStep 5: Searching for points")
    search_query = {
        "filter": {
            "must": [
                {"key": "source", "match": {"value": "dossieclean_test"}}
            ]
        },
        "limit": 10
    }
    
    response = requests.post(
        f"{QDRANT_URL}/collections/{collection_name}/points/scroll",
        headers=headers,
        json=search_query
    )
    
    if response.status_code != 200:
        print(f"Failed to search for points: {response.text}")
        return
    
    print(f"Search results: {json.dumps(response.json(), indent=2)}")
    
    print("\nQdrant connection test completed successfully!")

if __name__ == "__main__":
    test_qdrant_connection()
