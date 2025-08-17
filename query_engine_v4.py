from pydantic import BaseModel, Field
import os
import re
from dotenv import load_dotenv
from Utils.ETL import ETL_XML
from Utils.postgre import connect_to_postgresql, insert_data_to_postgresql, insert_conversation_to_postgresql, search_postgresql, convert_mongodb_to_postgresql_data, delete_postgresql_table, create_postgresql_table
from langfuse import get_client
import autogen
from autogen import AssistantAgent, UserProxyAgent
from autogen.agentchat.contrib.capabilities import transform_messages, transforms
from fastmcp import Client
from openinference.instrumentation.crewai import CrewAIInstrumentor
from openinference.instrumentation.litellm import LiteLLMInstrumentor

class MessageType(BaseModel):  
    message_type: int = Field(..., description="0 if the user's query is unrelated to the database, 1 if it is related")

class Query(BaseModel):
    Query: str = Field(..., description="The query")

CrewAIInstrumentor().instrument(skip_dep_check=True)
LiteLLMInstrumentor().instrument()

# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gv.json"

# llm = init_chat_model(
#     "gemini-2.5-flash",
#     model_provider="google-vertexai",
#     location="us-central1"
# )

load_dotenv()
# llm = init_chat_model("google_genai:gemini-2.5-flash")

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

config_list_gemini = autogen.config_list_from_json(
    "OAI_CONFIG_LIST2",
    filter_dict={
        "model": ["gemini-2.5-flash"],
    },
)

seed = 42

mcp_client = Client("http://127.0.0.1:9000/mcp")

router_agent = AssistantAgent(
        name="router_agent",
        system_message="""You are a helpful assistant that classifies the intent of the user's request as database related (SQLQuery) or unrelated (generic requests). Example of database requests: 'Which users were kicked out of the group', 'Were any accounts created', 'What time did jefferson join the meeting', etc...""",
        llm_config={"config_list": config_list_gemini, "seed": seed, "response_format": MessageType},
        max_consecutive_auto_reply=1
)

sql_agent = AssistantAgent(
            name="sql_agent",
            system_message=SQL_SYSTEM_PROMPT,
            llm_config={"config_list": config_list_gemini, "seed": seed, "response_format": Query},
            max_consecutive_auto_reply=1
        )

greeting_agent = AssistantAgent(
            name="greeting_agent",
            system_message=GENERIC_SYSTEM_PROMPT,
            llm_config={"config_list": config_list_gemini, "seed": seed},
            max_consecutive_auto_reply=1
        )

user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=0,
    code_execution_config=False,
)

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

async def set_conversation_id(new_conversation_id):
    global conversation_id, messages, user_proxy, sql_agent, mcp_client
    conversation_id = new_conversation_id

    messages_data = []
    async with mcp_client:
        messages_data = await mcp_client.call_tool("get_history", {"conversation_id": conversation_id})
        messages_data = messages_data.content
    if messages_data:
        for message in messages_data:
            user_proxy.send(message=message["user_query"], recipient=sql_agent, request_reply=False, silent=True)
            user_proxy.send(message=message["user_query"], recipient=greeting_agent, request_reply=False, silent=True)

context_handling = transform_messages.TransformMessages(
    transforms=[
        transforms.MessageHistoryLimiter(max_messages=5)
    ]
)
router_context_handling = transform_messages.TransformMessages(
    transforms=[
        transforms.MessageHistoryLimiter(max_messages=3)
    ]
)

context_handling.add_to_agent(sql_agent)
router_context_handling.add_to_agent(router_agent)
context_handling.add_to_agent(greeting_agent)

def search(query: str):
    global messages, conversation_id, postgre_client, table_name, min_score
    messages.append({"role": "user", "content": query})
    print("\n\nMessages History: ", messages)

    user_proxy.initiate_chat(
        router_agent,
        message=f"""
        Route this message: {query}""",
        clear_history=False
    )

    chat_history = user_proxy.chat_messages[router_agent]
    _query = MessageType.model_validate_json(chat_history[-1]["content"].strip())
    print("\n\nMessage Type: ", _query.message_type)

    print("message type", _query.message_type)
    if (_query.message_type == 0):
        user_proxy.initiate_chat(
            greeting_agent,
            message=query,
            clear_history=False
        )
        chat_history = user_proxy.chat_messages[greeting_agent]
        _query = chat_history[-1]["content"].strip()
        print("Response: ", _query)
        insert_conversation_to_postgresql(postgre_client, "conversations", [{"id": conversation_id, "user_query": query, "assistant_response": _query}])
        return _query
    
    
    user_proxy.initiate_chat(
        sql_agent,
        message=query,
        clear_history=False
    )

    chat_history = user_proxy.chat_messages[sql_agent]
    _query = Query.model_validate_json(chat_history[-1]["content"].strip())
    print("\n\nResponse: ", _query.Query)
    insert_conversation_to_postgresql(postgre_client, "conversations", [{"id": conversation_id, "user_query": query, "assistant_response": _query.Query}])
    _query = _query.Query

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