import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastmcp import FastMCP
from fastmcp.tools import Tool
import sys
from pydantic import Field
from Utils.postgre import connect_to_postgresql, fetch_conversation_from_postgres, insert_data_to_postgresql, create_conversations_table


history_mcp = FastMCP("MCP History")

@history_mcp.tool()
def get_history(conversation_id: str):
    postgre_client = connect_to_postgresql()
    create_conversations_table(postgre_client, "conversations", {"id": "str", "user_query": "str", "assistant_response": "str"})

    conversation_history = fetch_conversation_from_postgres(postgre_client, "conversations", conversation_id)
    return conversation_history

if __name__ == "__main__":
    history_mcp.run(transport="streamable-http", port=9000, path="/mcp")
