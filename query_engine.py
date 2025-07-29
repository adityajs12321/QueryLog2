from pymongo import MongoClient
from datetime import datetime
from pydantic import BaseModel, Field
import os
from google import genai
from bs4 import BeautifulSoup
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
        
        # Handle nested objects by converting to JSON strings
        for key, value in doc.items():
            if isinstance(value, dict):
                doc[key] = json.dumps(value)
            elif isinstance(value, list):
                doc[key] = json.dumps(value)
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