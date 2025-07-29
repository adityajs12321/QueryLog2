from pymongo import MongoClient
from elasticsearch import Elasticsearch, helpers
from datetime import datetime
from pydantic import BaseModel, Field
import os
from google import genai
import time
import re
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import ast
import psycopg2
import json

def gemini_response(client: genai.Client, messages: list, model: str, format=None) -> str:
    chat_history = []
    for message in messages[:len(messages) - 1]:
        chat_history.append(
            {
                "role": "model" if (message["role"] == "system" or message["role"] == "assistant") else message["role"],
                "parts": [
                    {
                        "text": message["content"]
                    }
                ]
            }
        )
    # print(chat_history)
    config = {}
    if (format != None): config = {"response_mime_type": "application/json", "response_schema": format}
    print(format)
    chat = client.chats.create(model=model, history=chat_history, config=config)
    response = chat.send_message(messages[-1]["content"])
    return response.text

class Query(BaseModel):
    Query: str = Field(..., description="The query")

def transform(record):
    return {
        "Timestamp": datetime.strptime(record[0], "%Y-%m-%d %H:%M:%S"),
        "EventID": record[1],
        "Description": record[2],
        "Username": record[3],
        "TargetAccount": record[4]
    }

def extract_tag_content(text: str, tag: str) -> list[str]:
    """
    Extracts all content enclosed by specified tags (e.g., <thought>, <response>, etc.).

    Parameters:
        text (str): The input string containing multiple potential tags.
        tag (str): The name of the tag to search for (e.g., 'thought', 'response').

    Returns:
        dict: A dictionary with the following keys:
            - 'content' (list): A list of strings containing the content found between the specified tags.
            - 'found' (bool): A flag indicating whether any content was found for the given tag.
    """
    # Build the regex pattern dynamically to find multiple occurrences of the tag
    tag_pattern = rf"<{tag}>(.*?)</{tag}>"

    # Use findall to capture all content between the specified tag
    matched_contents = re.findall(tag_pattern, text, re.DOTALL)

    return [content.strip() for content in matched_contents]

def ETL_XML(xml_file):
    events = BeautifulSoup(xml_file, "xml")
    events = events.findAll("Event")
    documents = []
    for event in events:
        document = {}
        document["ProviderName"] = event.find("Provider").get("Name")
        document["EventID"] = int(event.find("EventID").text)
        document["Version"] = int(event.find("Version").text)
        document["Level"] = int(event.find("Level").text)
        document["Task"] = int(event.find("Task").text)
        document["Opcode"] = event.find("Opcode").text
        document["Keywords"] = event.find("Keywords").text
        document["TimeCreated"] = datetime.strptime(event.find("TimeCreated").get("SystemTime"), "%Y-%m-%d %H:%M:%S")
        document["EventRecordID"] = int(event.find("EventRecordID").text)
        document["Channel"] = event.find("Channel").text
        document["Computer"] = event.find("Computer").text
        # document["Security"] = event.find("Security")
        event_data = event.find("EventData")

        if event_data:
            for data_item in event_data.find_all("Data"):
                document[data_item.get("Name")] = data_item.text
        
        documents.append(document)
    return documents

def connect_to_mongodb():
    """Establishes a connection to MongoDB."""
    try:
        # Adjust connection string as needed
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
    
def connect_to_postgresql():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname="adityajs",
            user="adityajs",
            password=os.environ["POSTGRE_PASS"],
            port="5432"
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Could not connect to PostgreSQL: {e}")
        return None
    
def convert_mongodb_to_postgresql_data(documents):
    """Converts MongoDB documents to PostgreSQL-compatible format."""
    converted_data = []
    
    for doc in documents:
        # Convert ObjectId to string
        
        # Handle nested objects by converting to JSON strings
        for key, value in doc.items():
            if isinstance(value, dict):
                doc[key] = json.dumps(value)
            elif isinstance(value, list):
                doc[key] = json.dumps(value)
            # Handle datetime objects
            elif isinstance(value, datetime):
                doc[key] = value.isoformat()
        
        converted_data.append({k: v for k,v in doc.items() if k != "_id"})
    print("converted_data", converted_data[0])
    return converted_data

def migrate_mongodb_to_postgresql(mongo_db_name, mongo_collection_name, postgres_table_name):
    """Main function to migrate data from MongoDB to PostgreSQL."""
    
    # Connect to databases
    mongo_client = connect_to_mongodb()
    pg_conn = connect_to_postgresql()
    
    if not mongo_client or not pg_conn:
        print("Failed to connect to one or both databases")
        return
    
    try:
        # Fetch data from MongoDB
        mongodb_data = fetch_data_from_mongodb(mongo_client, mongo_db_name, mongo_collection_name)
        
        if not mongodb_data:
            print("No data found in MongoDB collection")
            return
        
        # Convert data format
        converted_data = convert_mongodb_to_postgresql_data(mongodb_data)

        delete_postgresql_table(pg_conn, postgres_table_name)
        
        # Create PostgreSQL table
        if create_postgresql_table(pg_conn, postgres_table_name, converted_data[0]):
            # Insert data
            insert_data_to_postgresql(pg_conn, postgres_table_name, converted_data)
        
    except Exception as e:
        print(f"Migration failed: {e}")
    
    finally:
        # Close connections
        if mongo_client:
            mongo_client.close()
        if pg_conn:
            pg_conn.close()
        print("Database connections closed")

def create_conversations_table(conn, table_name, sample_document):
    """Creates a PostgreSQL table based on MongoDB document structure."""
    if not conn or not sample_document:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Build CREATE TABLE statement
        columns = []
        for key, value in sample_document.items():
            if isinstance(value, int):
                columns.append(f"{key} INTEGER")
            elif isinstance(value, float):
                columns.append(f"{key} REAL")
            elif isinstance(value, bool):
                columns.append(f"{key} BOOLEAN")
            elif isinstance(value, datetime):
                columns.append(f"{key} DATE")
            else:
                columns.append(f"{key} TEXT")
        
        create_query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {', '.join(columns)}
        )
        """
        
        cursor.execute(create_query)
        # cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_search_vector ON {table_name} USING GIN(search_vector)")
        conn.commit()
        cursor.close()
        print(f"Table '{table_name}' created successfully")
        return True
        
    except psycopg2.Error as e:
        print(f"Error creating table: {e}")
        conn.rollback()
        return False
    
def create_postgresql_table(conn, table_name, sample_document):
    """Creates a PostgreSQL table based on MongoDB document structure."""
    if not conn or not sample_document:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Build CREATE TABLE statement
        columns = []
        for key, value in sample_document.items():
            if isinstance(value, int):
                columns.append(f"{key} INTEGER")
            elif isinstance(value, float):
                columns.append(f"{key} REAL")
            elif isinstance(value, bool):
                columns.append(f"{key} BOOLEAN")
            elif isinstance(value, datetime):
                columns.append(f"{key} DATE")
            else:
                columns.append(f"{key} TEXT")
        
        create_query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {', '.join(columns)},
            search_vector TSVECTOR
        )
        """
        
        cursor.execute(create_query)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_search_vector ON {table_name} USING GIN(search_vector)")
        conn.commit()
        cursor.close()
        print(f"Table '{table_name}' created successfully")
        return True
        
    except psycopg2.Error as e:
        print(f"Error creating table: {e}")
        conn.rollback()
        return False
    
def delete_postgresql_table(conn, table_name):
    """Deletes a specified table from PostgreSQL."""
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        cursor.execute(f"DROP INDEX IF EXISTS idx_{table_name}_search_vector")
        conn.commit()
        cursor.close()
        print(f"Table '{table_name}' deleted successfully")
        return True
    except psycopg2.Error as e:
        print(f"Error deleting table: {e}")
        conn.rollback()
        return False

def insert_conversation_to_postgresql(conn, table_name, data):
    """Inserts data into PostgreSQL table."""
    if not conn or not data:
        return
    
    try:
        cursor = conn.cursor()
        
        # Get column names from first document
        columns = list(data[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        
        insert_query = f"""
        INSERT INTO {table_name}
        VALUES ({placeholders})
        """
        
        # Prepare data for insertion
        values_list = []
        for doc in data:
            values = [doc.get(col) for col in columns]
            values_list.append(values)
        
        # Execute batch insert
        cursor.executemany(insert_query, values_list)
        conn.commit()
        cursor.close()
        print(f"Successfully inserted {len(data)} records into PostgreSQL")
        
    except psycopg2.Error as e:
        print(f"Error inserting data: {e}")
        conn.rollback()

def insert_data_to_postgresql(conn, table_name, data):
    """Inserts data into PostgreSQL table."""
    if not conn or not data:
        return
    
    try:
        cursor = conn.cursor()
        
        # Get column names from first document
        columns = list(data[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        
        insert_query = f"""
        INSERT INTO {table_name}
        VALUES ({placeholders}, to_tsvector('english', %s))
        """
        
        # Prepare data for insertion
        values_list = []
        for doc in data:
            values = [doc.get(col) for col in columns]
            values.append(values[-1])
            values_list.append(values)
        
        # Execute batch insert
        cursor.executemany(insert_query, values_list)
        conn.commit()
        cursor.close()
        print(f"Successfully inserted {len(data)} records into PostgreSQL")
        
    except psycopg2.Error as e:
        print(f"Error inserting data: {e}")
        conn.rollback()

def fetch_conversation_from_postgres(conn, table_name, conversation_id):
    """Fetches data from a specified table in PostgreSQL."""
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = {conversation_id}")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        return [dict(zip(columns, row)) for row in rows]
    except psycopg2.Error as e:
        print(f"Error fetching data from PostgreSQL: {e}")
        return []
    
def search_postgresql(conn, query):
    """Performs a search in PostgreSQL."""

    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        return rows
    except psycopg2.Error as e:
        print(f"Error fetching data from PostgreSQL: {e}")
        return []


def connect_to_elasticsearch():
    """Establishes a connection to Elasticsearch."""
    es = Elasticsearch(hosts=["https://localhost:9200"], basic_auth=["elastic", "vkGS-g1kirw7OO-pobRo"], verify_certs=False, ssl_show_warn=False)
    if es.ping():
        print("Connected to Elasticsearch")
        return es
    else:
        print("Could not connect to Elasticsearch")
        return None

def create_index(es_client: Elasticsearch, index_name):
    """Creates an Elasticsearch index if it doesn't exist."""

    if es_client.indices.exists(index=index_name):
        es_client.indices.delete(index=index_name)
    
    try:
        # es_client.indices.create(index=index_name)
        mapping = {'mappings': {'properties': {'Action': {'type': 'text', 'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}}, "Action_vector": {"type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"}, 'Channel': {'type': 'text', 'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}}, 'Computer': {'type': 'text', 'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}}, 'EventID': {'type': 'long'}, 'EventRecordID': {'type': 'long'}, 'Keywords': {'type': 'text', 'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}}, 'Level': {'type': 'long'}, 'Opcode': {'type': 'text', 'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}}, 'ProviderName': {'type': 'text', 'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}}, 'SubjectUserName': {'type': 'text', 'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}}, 'TargetUserName': {'type': 'text', 'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}}, 'Task': {'type': 'long'}, 'TimeCreated': {'type': 'date'}, 'Version': {'type': 'long'}}}}
        es_client.indices.create(index=index_name, body=mapping)
        print(f"Index '{index_name}' created")
    except Exception as e:
        print(f"Error creating index: {e}")

def index_data_to_elasticsearch(es_client, model, index_name, data):
    """Indexes data into the specified Elasticsearch index."""
    if not es_client or not data:
        return
    actions = []
    for record in data:
        embedding = model.encode(record.get("Action"))
        record["Action_vector"] = embedding.tolist()  # Convert numpy array to list for JSON serialization
        action = {
            "_index": index_name,
            "_source": record
        }
        actions.append(action)

    try:
        helpers.bulk(es_client, actions)
        print("Data indexed successfully")
    except helpers.BulkIndexError as e:
        print(f"Error indexing data: {e}")

def getvalue(nested_dict, value, prepath=()):
    for k, v in nested_dict.items():
        path = prepath + (k,)
        if k == value: # found value
            return v
        elif hasattr(v, 'items'): # v is a dict
            p = getvalue(v, value, path) # recursive call
            if p is not None:
                return p

def setvalue(nested_dict, value, set_value):
    for k, v in nested_dict.items():
        if k == value: # found value
            nested_dict[k] = set_value
            return None
        elif hasattr(v, 'items'): # v is a dict
            setvalue(nested_dict[k], value, set_value) # recursive call

def switch_to_knn(nested_dict, model):
    for k, v in nested_dict.items():
        if k == "match": # found value
            if ("Action" in list(v.keys())):
                embedded_message = model.encode(nested_dict[k]["Action"])
                nested_dict["knn"] = {
                        "field": "Action_vector",
                        "query_vector": embedded_message.tolist(),
                        "k": 50,
                        "num_candidates": 100
                    }
                
                del nested_dict[k]
            return None
        elif hasattr(v, 'items'): # v is a dict
            switch_to_knn(nested_dict[k], model) # recursive call
        elif isinstance(v, list):
            for i in range(len(v)):
                if v[i].get("match") is not None:
                    if (list(v[i].get("match").keys())[0] == "Action"):
                        embedded_message = model.encode(nested_dict[k][i]["match"]["Action"])
                        nested_dict[k][i] = {"knn": {
                            "field": "Action_vector",
                            "query_vector": embedded_message.tolist(),
                            "k": 50,
                            "num_candidates": 100
                        }}
                        return None

def search_documents(es_client, model, index_name, query):
    """
    Searches for documents in the specified index using the given query.
    """
    if not es_client:
        return
    
    # query_string = getvalue(query, "Action")
    # if query_string is not None:
    #     encoded_string = model.encode(query_string)
    #     setvalue(query, "Action", encoded_string.tolist())

    search_results = []
    try:
        response = es_client.search(index=index_name, body=query)
        # Extract the actual documents from the response
        hits = response['hits']['hits']
        aggregations = response.get("aggregations")
        print(f"Found {len(hits)} documents:")
        if hits == []:
            return search_results
        
        if (aggregations == None):
            for hit in hits:
                search_results.append(hit['_source'])
                # Each hit contains the document in the _source field
                print(hit['_source'])
        else:
            # print(aggregations)
            for bucket in list(aggregations.values()):
                if (bucket.get("buckets") is not None):
                    search_results.append(bucket["buckets"])
                    print(bucket["buckets"])
                elif (bucket.get("value_as_string") is not None):
                    search_results.append(bucket["value_as_string"])
                    print(bucket["value_as_string"])
        
        return search_results
    except Exception as e:
        print(f"An error occurred: {e}")


llm = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

#UNSTRUCTURED LOGS SYSTEM PROMPT
SYSTEM_PROMPT = """
You are a PostgreSQL agent that generates an PostgreSQL query that answers the user's question. Format the output in JSON.
Here is the table structure:

ProviderName: str, EventID: int, Version: int, Level: int, Task: int, Opcode: str, Keywords: str, TimeCreated: date, EventRecordID: int, Channel: str, Computer: str, SubjectUserName: str, TargetUserName: str, Action: str; Action is the description of the event.
Action has a search vector associated with it.

Example Usage:

User: "Return all records that are associated with the computer ztran.corp.local"
Response: "SELECT * FROM unstructured_logs WHERE Computer = 'ztran.corp.local';"

User: "Who was removed from the security enabled local group"
Response: "SELECT SubjectUserName FROM unstructured_logs WHERE search_vector @@ plainto_tsquery('english', 'removed from the security enabled local group');"

User: "What time did natalierivera create an account"
Response: "SELECT TimeCreated FROM unstructured_logs WHERE SubjectUserName = 'natalierivera' AND WHERE search_vector @@ plainto_tsquery('english', 'created account');"

Don' forget to add "query" to the start of the query.
Follow JSON structure strictly.
"""

messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

conversation_id = 0
postgre_client = connect_to_postgresql()

def set_conversation_id(new_conversation_id):
    global conversation_id, messages
    conversation_id = new_conversation_id

    create_conversations_table(postgre_client, "conversations", {"id": new_conversation_id, "user_query": "str", "assistant_response": "str"})
    messages_data = fetch_conversation_from_postgres(postgre_client, "conversations", conversation_id)
    if messages_data:
        for message in messages_data:
            messages.append({"role": "user", "content": message["user_query"]})

    if len(messages) > 6:
        messages[1:] = messages[-5:]

def search(query: str):
    global messages, conversation_id, postgre_client
    messages.append({"role": "user", "content": query})

    response = gemini_response(llm, messages, "gemini-2.5-flash", Query)

    response = Query.model_validate_json(response)

    _query = response.Query
    print("\n\nResponse: ", _query)
    

    insert_conversation_to_postgresql(postgre_client, "conversations", [{"id": conversation_id, "user_query": query, "assistant_response": _query}])

    migrate_mongodb_to_postgresql("Logs", "unstructured_logs", "unstructured_logs")

    return search_postgresql(postgre_client, _query)

if __name__ == "__main__":
    # while True:
        message = input("> ")
        messages.append({"role": "user", "content": message})


        # llm.format = Query.model_json_schema()
        # response = llm.invoke(messages)

        response = gemini_response(llm, messages, "gemini-2.5-flash", Query)

        response = Query.model_validate_json(response)

        query = response.Query
        print("\n\nResponse: ", query)

        insert_conversation_to_postgresql(postgre_client, "conversations", [{"id": conversation_id, "user_query": message, "assistant_response": query}])

        migrate_mongodb_to_postgresql("Logs", "unstructured_logs", "unstructured_logs")

        print(search_postgresql(postgre_client, query))

        # query = ast.literal_eval(query)

        # switch_to_knn(query, model)
        # query["_source"] = {"excludes": ["Action_vector"]}
        # query["min_score"] = 0.9

        # mongo_client = connect_to_mongodb()

        # if mongo_client:
        #         # Fetch data from PostgreSQL
        #     # with open("ad_simulated_events.xml", "r") as file:
        #     #     data = file.read()
        #     #     xml_file = ETL_XML(data)
        #     #     insert_into_mongodb(mongo_client, "Logs", "unstructured_logs", xml_file)

        #     mongodb_data = fetch_data_from_mongodb(mongo_client, "Logs", "unstructured_logs")
        #     mongo_client.close()

        #     if mongodb_data:
        #         # Elasticsearch connection details
        #         es = connect_to_elasticsearch()
        #         if es:
        #             index_name = "unstructured_logs_index"
                    
        #             create_index(es, index_name)
                    
        #             # Index the data
        #             index_data_to_elasticsearch(es, model, index_name, mongodb_data)
        #             time.sleep(1)

        #             search_results = []
        #             while True:
        #                 search_results = search_documents(es, model, index_name, query)
        #                 if (search_results == []):
        #                     query["min_score"] = query["min_score"] - 0.05
        #                 else:
        #                     query["min_score"] = 0.9
        #                     break