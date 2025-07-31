import psycopg2
import os
import json
from datetime import datetime
from Utils.mongo import connect_to_mongodb, fetch_data_from_mongodb

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
    # print("converted_data", converted_data[0])
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

        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        
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
        print(f"Successfully inserted {len(data)} records")
        
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
        print(f"Successfully inserted {len(data)} records")
        
    except psycopg2.Error as e:
        print(f"Error inserting data: {e}")
        conn.rollback()

def store_data_to_postgresql(conn, table_name, data):
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
        print(f"Successfully inserted {len(data)} records")
        
    except psycopg2.Error as e:
        print(f"Error inserting data: {e}")
        conn.rollback()

def fetch_conversation_from_postgres(conn, table_name, conversation_id):
    """Fetches data from a specified table in PostgreSQL."""
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = '{conversation_id}'")
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