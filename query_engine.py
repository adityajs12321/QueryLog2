from pydantic import BaseModel, Field
import os
from google import genai
from Utils.ETL import ETL_XML
from Utils.postgre import connect_to_postgresql, create_conversations_table, fetch_conversation_from_postgres, insert_conversation_to_postgresql, search_postgresql, convert_mongodb_to_postgresql_data, store_data_to_postgresql

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
Response: "SELECT TargetUserName FROM unstructured_logs WHERE search_vector @@ plainto_tsquery('english', 'removed from the security enabled local group');"

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

    create_conversations_table(postgre_client, "conversations", {"id": "str", "user_query": "str", "assistant_response": "str"})
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
    
    with open("ad_simulated_events.xml", "r") as file:
        data = ETL_XML(file)
        converted_data = convert_mongodb_to_postgresql_data(data)

        insert_conversation_to_postgresql(postgre_client, "conversations", [{"id": conversation_id, "user_query": query, "assistant_response": _query}])

        store_data_to_postgresql(postgre_client, "unstructured_logs", converted_data)

    return search_postgresql(postgre_client, _query)