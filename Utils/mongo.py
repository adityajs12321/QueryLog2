from pymongo import MongoClient

def connect_to_mongodb():
    """Establishes a connection to MongoDB."""
    try:
        client = MongoClient("mongodb://localhost:27017/")
        # Test connection
        client.admin.command('ping')
        print("Connected to MongoDB")
        return client
    except Exception as e:
        print(f"Could not connect to MongoDB: {e}")
        return None
    
def insert_into_mongodb(client: MongoClient, db_name, collection_name, documents):
    """Inserts data into MongoDB."""

    try:
        db = client[db_name]
        collection = db[collection_name]

        collection.insert_many(documents)
        print(f"Inserted {len(documents)} documents into MongoDB collection: {collection_name}")
    except Exception as e:
        print(f"Error inserting data into MongoDB: {e}")
        return None

def fetch_data_from_mongodb(client, db_name, collection_name):
    """Fetches data from MongoDB collection."""
    if not client:
        return []
    
    try:
        db = client[db_name]
        collection = db[collection_name]
        
        # Fetch all documents
        documents = list(collection.find())
        documents = [{k: v for k,v in document.items() if k != "_id"} for document in documents]
        print(f"Fetched {len(documents)} documents from MongoDB")
        return documents
    except Exception as e:
        print(f"Error fetching data from MongoDB: {e}")
        return []