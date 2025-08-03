from pydantic import BaseModel, Field
import os
import re
from google import genai
from Utils.ETL import ETL_XML
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from Utils.postgre import connect_to_postgresql, create_conversations_table, fetch_conversation_from_postgres, insert_data_to_postgresql, insert_conversation_to_postgresql, search_postgresql, convert_mongodb_to_postgresql_data, store_data_to_postgresql, delete_postgresql_table, create_postgresql_table

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
    ResponseType: int = Field(..., description="0 if the user's query is unrelated to the database, 1 if it is related")
    Query: str = Field(..., description="The query")


llm = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

#UNSTRUCTURED LOGS SYSTEM PROMPT
SYSTEM_PROMPT = """
You are a PostgreSQL agent that generates an PostgreSQL query that answers the user's question.
Here is the table structure:

ProviderName: str, EventID: int, Version: int, Level: int, Task: int, Opcode: str, Keywords: str, TimeCreated: date, EventRecordID: int, Channel: str, Computer: str, SubjectUserName: str, TargetUserName: str, Action: str; Action is the description of the event.

Example Usage:

User: "Return all records that are associated with the computer ztran.corp.local"
Response: "SELECT * FROM unstructured_logs WHERE Computer = 'ztran.corp.local';"

User: "Who was removed from the security enabled local group"
Response: "SELECT TargetUserName FROM unstructured_logs WHERE similarity(Action, 'removed from the security enabled local group') > *score*;"

User: "What time did natalierivera create an account"
Response: "SELECT TimeCreated FROM unstructured_logs WHERE SubjectUserName = 'natalierivera' AND similarity(Action, 'create account') > *score*;"

Don' forget to add "query" to the start of the query and use *score* for similarity search.

Additional constraints:
- If the user's query is not related to the database, say that you are an SQL agent and explain your purpose.
- FOCUS ON THE LAST MESSAGE
"""

messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

conversation_id = 0
postgre_client = connect_to_postgresql()

table_name = "unstructured_logs"
min_score = 0.6

with open("ad_simulated_events.xml", "r") as file:
    data = ETL_XML(file)
    converted_data = convert_mongodb_to_postgresql_data(data)
    delete_postgresql_table(postgre_client, table_name)
    create_postgresql_table(postgre_client, table_name, data[0])
    insert_data_to_postgresql(postgre_client, table_name, converted_data)

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
    # print("\n\nMessages History: ", messages)

def search(query: str):
    global messages, conversation_id, postgre_client, table_name, min_score
    messages.append({"role": "user", "content": query})
    print("\n\nMessages History: ", messages)

    response = gemini_response(llm, messages, "gemini-2.5-flash", Query)

    response = Query.model_validate_json(response)

    _query = response.Query
    print("\n\nResponse: ", _query)

    insert_conversation_to_postgresql(postgre_client, "conversations", [{"id": conversation_id, "user_query": query, "assistant_response": _query}])

    if (response.ResponseType == 0):
        return response.Query

    match = re.search(r'\*score\*', _query)
    keyword = match.group(0) if match else None
    if not keyword:
        results =  search_postgresql(postgre_client, _query)
        if (results == []):
            return "No records found."
        return results
    else:
        print("Keyword found")
        temp_query = _query.replace(keyword, str(min_score))
        while True:
            results = search_postgresql(postgre_client, temp_query)
            if results:
                min_score = 0.6
                return results
            else:
                print("Reducing score to", min_score)
                min_score -= 0.1
                if min_score <= 0:
                    min_score = 0.6
                    return "No records found."
                temp_query = _query.replace(keyword, str(min_score))