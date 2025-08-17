from pydantic import BaseModel, Field
import os
import re
from dotenv import load_dotenv
from Utils.ETL import ETL_XML
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from Utils.postgre import connect_to_postgresql, create_conversations_table, fetch_conversation_from_postgres, insert_data_to_postgresql, insert_conversation_to_postgresql, search_postgresql, convert_mongodb_to_postgresql_data, delete_postgresql_table, create_postgresql_table
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict, Annotated
from langfuse.langchain import CallbackHandler

class MessageType(BaseModel):  
    message_type: int = Field(..., description="0 if the user's query is unrelated to the database, 1 if it is related")

class Query(BaseModel):
    Query: str = Field(..., description="The query")

# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gv.json"

# llm = init_chat_model(
#     "gemini-2.5-flash",
#     model_provider="google-vertexai",
#     location="us-central1"
# )

load_dotenv()
llm = init_chat_model("google_genai:gemini-2.5-flash")

#UNSTRUCTURED LOGS SYSTEM PROMPT
SQL_SYSTEM_PROMPT = """
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
- FOCUS ON THE LAST MESSAGE
"""

GENERIC_SYSTEM_PROMPT = """
You are a helpful assistant that handles generic user requests that are not related to SQL queries or databases.
If the user asks for something that is unrelated to SQL queries or databases, you should say ONLY describe your purpose and not generate any SQL queries.
"""

class State(TypedDict):
    messages: Annotated[list[dict], add_messages]
    message_type: str | None

graph_builder = StateGraph(State)

def classify_intent(state: State) -> str:
    last_message = state["messages"][-1]
    model = llm.with_structured_output(MessageType)

    messages = [
        {"role": "system", "content": """You are a helpful assistant that classifies the intent of the user's request as database related (SQLQuery) or unrelated (generic requests). Example of database requests: 'Which users were kicked out of the group', 'Were any accounts created', 'What time did jefferson join the meeting', etc..."""},
        {"role": "user", "content": last_message.content}
    ]

    message_type = model.invoke(messages)

    return {"message_type": message_type.message_type}

def router(state: State) -> str:
    if state["message_type"] == 0:
        return {"next": "generic_agent"}
    else:
        return {"next": "sql_agent"}
    
def sql_agent(state: State) -> str:
    if (len(state["messages"]) > 6):
        last_message = state["messages"][-5:]
    else:
        last_message = state["messages"]
    
    model = llm.with_structured_output(Query)

    messages = [
        {"role": "system", "content": SQL_SYSTEM_PROMPT},
    ]
    messages.extend(last_message)

    response = model.invoke(messages)

    return {"messages": [{"role": "assistant", "content": response.Query}]}

def generic_agent(state: State) -> str:
    if (len(state["messages"]) > 6):
        last_message = state["messages"][-5:]
    else:
        last_message = state["messages"]

    messages = [
        {"role": "system", "content": GENERIC_SYSTEM_PROMPT},
    ]
    messages.extend(last_message)

    response = llm.invoke(messages)

    return {"messages": [{"role": "assistant", "content": response.content}]}

langfuse_handler = CallbackHandler()

graph_builder.add_node("classifier", classify_intent)
graph_builder.add_node("router", router)
graph_builder.add_node("sql_agent", sql_agent)
graph_builder.add_node("generic_agent", generic_agent)


graph_builder.add_edge(START, "classifier")
graph_builder.add_edge("classifier", "router")
graph_builder.add_conditional_edges(
    "router",
    lambda state: state["next"],
    {
        "sql_agent": "sql_agent",
        "generic_agent": "generic_agent"
    }
)
graph_builder.add_edge("sql_agent", END)
graph_builder.add_edge("generic_agent", END)

graph = graph_builder.compile()

conversation_id = 0
postgre_client = connect_to_postgresql()
table_name = "unstructured_logs"
min_score = 0.6

messages = []

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
    messages = []
    if messages_data:
        for message in messages_data:
            messages.append({"role": "user", "content": message["user_query"]})

def search(query: str):
    global messages, conversation_id, postgre_client, table_name, min_score
    messages.append({"role": "user", "content": query})
    print("\n\nMessages History: ", messages)

    response = graph.invoke({"messages": messages}, config={"callbacks": [langfuse_handler]})

    _query = response["messages"][-1].content
    print("\n\nResponse: ", _query)

    insert_conversation_to_postgresql(postgre_client, "conversations", [{"id": conversation_id, "user_query": query, "assistant_response": _query}])

    print("message type", response["message_type"])
    if (response["message_type"] == 0):
        return _query

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
            if results or results == [(0,)]:
                min_score = 0.6
                return results
            else:
                print("Reducing score to", min_score)
                min_score -= 0.1
                if min_score <= 0:
                    min_score = 0.6
                    return "No records found."
                temp_query = _query.replace(keyword, str(min_score))