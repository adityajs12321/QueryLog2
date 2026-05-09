import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent, BaseAgent, LlmAgent
from google.adk.sessions import DatabaseSessionService
from dotenv import load_dotenv
import io
import math
from contextlib import redirect_stdout
import json, os
from numpy import generic
import psycopg2
from urllib.parse import quote_plus
from typing import Optional, override
from google.adk.sessions.base_session_service import GetSessionConfig, Session
from google.adk.agents.invocation_context import InvocationContext
from typing import AsyncGenerator
from google.adk.events.event import Event
from torch import mul
from google.generativeai import GenerativeModel

load_dotenv()

class LimitedContextDatabaseSessionService(DatabaseSessionService):
    """
    A DatabaseSessionService that limits the number of events returned by get_session,
    and filters out function call events from the context sent to the LLM.
    """

    def __init__(self, db_url: str, max_recent_events_for_llm: int = 5, filter_function_calls: bool = True):
        super().__init__(db_url=db_url)
        self.max_recent_events_for_llm = max_recent_events_for_llm
        self.filter_function_calls = filter_function_calls

    def _should_filter_event(self, event: Event) -> bool:
        """
        Determines if an event should be filtered out from the context.
        
        Args:
            event: The event to check
            
        Returns:
            True if the event should be filtered out, False otherwise
        """
        if not self.filter_function_calls:
            return False
            
        # Filter out events that contain function calls
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    return True
        
        return False

    @override
    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:

        # First get the session with a higher event limit to account for filtering
        temp_config = config
        original_limit = self.max_recent_events_for_llm

        if temp_config is None:
            # Request more events than needed to account for filtering
            temp_config = GetSessionConfig(num_recent_events=self.max_recent_events_for_llm * 2)
        elif temp_config.num_recent_events is None:
            temp_config.num_recent_events = self.max_recent_events_for_llm * 2
        elif temp_config.num_recent_events > 0:
            # Double the requested events to account for filtering
            temp_config.num_recent_events = min(temp_config.num_recent_events * 2, 50)  # Cap at 50

        # Get the session with the temporary config
        session = await super().get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            config=temp_config
        )

        if session and self.filter_function_calls and session.events:
            # Filter out function call events
            filtered_events = []
            for event in session.events:
                if not self._should_filter_event(event):
                    filtered_events.append(event)
                    
            # Limit to the requested number of events after filtering
            if len(filtered_events) > original_limit:
                filtered_events = filtered_events[-original_limit:]
                
            # Replace the events in the existing session object to preserve all metadata
            session.events = filtered_events

        return session

# Create a weather tool that returns weather given latitude and longitude
def get_weather(latitude: str, longitude: str) -> dict:
    """Returns the weather for given latitude and longitude.
    
    Args:
        latitude (str): Latitude of the location.
        longitude (str): Longitude of the location.

    Returns:
        dict: status and result or error msg.
    """
    response = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,wind_speed_10m"
    )

    data = response.json()
    return data

def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """

    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": (
                f"Sorry, I don't have timezone information for {city}."
            ),
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = (
        f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
    )
    return {"status": "success", "report": report}

# Python execution tool
def run_python(code: str) -> dict:
    """Safely executes simple Python code and returns the result.

    Guidance for the agent:
    - Use this tool when the user asks to run Python, do calculations, or manipulate data.
    - The code can assign a variable named `result` or print output. The tool will return either
      the `result` variable (if present) or captured stdout.
    - Dangerous operations (imports, filesystem, networking, subprocesses, dunders) are blocked.

    Args:
        code (str): Python code to execute. Prefer pure computation with standard operations.

    Returns:
        dict: status and report or error message.
    """

    banned_substrings = [
        "import ", "__", "open(", "os.", "sys.", "subprocess", "socket.", "eval(", "exec(", "globals(", "locals("
    ]
    lowered = code.lower()
    for token in banned_substrings:
        if token in lowered:
            return {
                "status": "error",
                "error_message": f"Disallowed operation detected in code: '{token.strip()}'."
            }

    safe_builtins = {
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "round": round,
    }

    globals_env = {"__builtins__": safe_builtins, "math": math}
    locals_env = {}

    stdout_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer):
            exec(code, globals_env, locals_env)
    except Exception as e:
        return {"status": "error", "error_message": f"Execution error: {e}"}

    if "result" in locals_env:
        return {"status": "success", "report": str(locals_env["result"]) }

    output = stdout_buffer.getvalue().strip()
    if output:
        return {"status": "success", "report": output}
    else:
        return {"status": "success", "report": "Code executed. No output produced."}

# @title Define Agent Interaction Function

from google.genai import types # For creating message Content/Parts
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
import asyncio

conn = psycopg2.connect(
            dbname="querylogconv",
            user="adityajs",
            password=os.environ["POSTGRE_PASS"],
            port="5432"
        )

postgre_password = os.environ["POSTGRE_PASS"]
        #   "postgresql+psycopg2://scott:tiger@localhost/test"
encoded_password = quote_plus(postgre_password)
db_url = f"postgresql+psycopg2://adityajs:{encoded_password}@localhost/querylogconv"
session_service = LimitedContextDatabaseSessionService(
    db_url=db_url, 
    max_recent_events_for_llm=5, 
    filter_function_calls=True  # This will filter out function call events from context
)

APP_NAME = "new_app2"
USER_ID = "adijs"
session_id = "session_027"


async def call_agent_async(query: str, runner: Runner, user_id, session_id):
  """Sends a query to the agent and prints the final response."""
  print(f"\n>>> User Query: {query}")

  content = types.Content(role='user', parts=[types.Part(text=query)])

  final_response_text = "Agent did not produce a final response."

  async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
      if event.is_final_response():
          if event.content and event.content.parts:
             # Extract only text parts to avoid the warning about non-text parts
             text_parts = []
             for part in event.content.parts:
                 if hasattr(part, 'text') and part.text:
                     text_parts.append(part.text)
             
             if text_parts:
                 final_response_text = ' '.join(text_parts)
             else:
                 # Fallback: if no text parts found, check if it's a function call response
                 if hasattr(event.content.parts[0], 'function_call'):
                     final_response_text = f"Function call executed: {event.content.parts[0].function_call.name}"
                 else:
                     final_response_text = "Response contains no text content."
          elif event.actions and event.actions.escalate:
             final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
          break

  return final_response_text

# Specialized agents
weather_agent = Agent(
    name="weather_time_agent",
    model="gemini-2.5-flash",
    description=(
        "Agent to answer questions about the time and weather in a city."
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about the time and weather in a city."
        "YOU CAN CONVERT THE CITY NAME TO LATITUDE AND LONGITUDE WITHOUT ANY TOOLS."
    ),
    tools=[get_weather, get_current_time],
)

generic_agent = Agent(
    name="generic_agent",
    model="gemini-2.5-flash",
    description=(
        "Helpful agent that can answer any question."
    ),
    instruction=(
        "You are a helpful agent that can answer any question."
    )
)

python_agent = Agent(
    name="python_agent",
    model="gemini-2.5-flash",
    description=(
        "Agent for running safe Python snippets and performing calculations."
    ),
    instruction=(
        "You are a helpful agent that executes small Python code snippets. Prefer using a variable named 'result' to return values, otherwise rely on printed output."
    ),
    tools=[run_python],
)

# Router agent (decides intent and calls the correct tool)
router_agent = Agent(
    name="router_agent",
    model="gemini-2.5-flash",
    description=(
        "Routes user requests to the appropriate capability: weather/time or Python execution."
    ),
    instruction=(
        "Decide user's intent first. If they ask about weather or current time in a city, call the corresponding weather/time tool.\n"
        "If they ask to compute, transform data, or run code, call the Python tool.\n"
        "Only call the tool that matches the user's intent. If unclear, ask a brief clarifying question."
    ),
    tools=[get_weather, get_current_time, run_python],
)

coder_agent = Agent(
    name="coder_agent",
    model="gemini-2.5-flash",
    description=(
        "You are a helpful AI assistant that generates Python code to create games using the Pygame library. "
    ),
    instruction=(
        "Generate a complete, executable Python script based on the user's game idea or request. "
        "The script should be self-contained, use Pygame, and include all necessary code to run the game. "
        "Do not require any external assets unless the user specifies them. "
        "If the user does not specify game dimensions, use 640x480 as the default window size. "
        "Do not include any code for installing packages. "
        "Your entire response should be only the Python code, enclosed in ```python ... ```"
    ),
    tools=[]  # No specific tool needed for this agent
)

assets_agent = Agent(
    name="assets_agent",
    model="gemini-2.5-flash",
    description=(
        "You are a helpful AI assistant that generates Python code to create images using the Pillow library."
    ),
    instruction=(
        "Your task is to generate a complete, executable Python script based on the user's request"
        "The generated code must be a complete Python script."
        "It MUST use the `Pillow` (PIL) library."
        "The script must save the final image to a file named 'generated_image.png'."
        "Do NOT include any code for displaying the image (e.g., `image.show()`), only save it."
        "Image save directory is 'assets/'"
        "The image dimensions should be 512x512 pixels unless the user specifies otherwise."
        "Do not write any code that performs file system operations other than saving the single image file (e.g., no reading files, deleting files, or listing directories)."
        "Image background should be transparent."
        "Do not include any code that makes network requests."
        "The generated code must be self-contained and not require any external assets."
        "Assume that `Pillow` is already installed."
        "Your entire response should be only the Python code, enclosed in ```python ... ```."
    ),
    tools=[]  # No specific tool needed for this agent
)

async def main_engine(query: str):
    global session_id
    # await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

    existing_sessions = await session_service.list_sessions(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    
    session_found = False

    # If there's an existing session, use it, otherwise create a new one
    if existing_sessions and len(existing_sessions.sessions) > 0:
        for session in existing_sessions.sessions:
            if session.id == session_id:
                print(f"Continuing existing session: {session_id}")
                session_found = True
                break
        
    if not session_found:
        # Create a new session with initial state
        new_session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id
        )
        print(f"Created new session: {session_id}")

    runner = Runner(
        agent=generic_agent, # Use the router agent as the entrypoint
        app_name=APP_NAME,
        session_service=session_service,   # Associates runs with our app
    )

    # query = input("Enter your query: ")
    # query = "whats my favourite color?"
    response = await call_agent_async(query, runner, USER_ID, session_id)

    # completed_session = await runner.session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    # print("\nCompleted session: \n", completed_session.events)

    code = response.strip()
    print(code)
    return code

    # return 2

summarize_agent = Agent(
    name="summarize_agent",
    model="gemini-2.5-flash",
    description=(
        "Agent to summarize user conversations."
    ),
    instruction=(
        "You are a helpful agent who can summarize user conversations."
        "Summarize it in such a way that the AI agent it gets passed to be understand the user's query"
    ),
    tools=[],
    output_key="summarized_response"
)

classify_history_agent = Agent(
    name="classify_history_agent",
    model="gemini-2.5-flash",
    description=(
        "Agent to classify user conversation history."
    ),
    instruction=(
        "You are a helpful agent who can classify user conversation history and route it to the appropriate agent."
        "Categories: 'weather', 'python', 'generic'"
    ),
    output_key="next_agent"
)

class OrchestratorAgent:
    """
    An orchestrator agent that routes user queries to specialized agents based on intent.
    """

    def __init__(
        self,
        name: str,
        summarize_agent: LlmAgent,
        classify_history_agent: LlmAgent,
        weather_agent: LlmAgent,
        python_agent: LlmAgent,
        generic_agent: LlmAgent,
    ):
        self.name = name
        self.summarize_agent = summarize_agent
        self.classify_history_agent = classify_history_agent
        self.weather_agent = weather_agent
        self.python_agent = python_agent
        self.generic_agent = generic_agent
    
    async def run_async(self, user_id: str, session_id: str, new_message):
        """
        Run the orchestrator logic without inheriting from BaseAgent
        """
        # For now, let's just route directly based on the message content
        message_text = new_message.parts[0].text.lower()

        # Summarize the context from the session using summarize_agent

        # Retrieve the session to get its events (context)
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )
        # Add the new user message as an event to the session
        # await session_service.append_event(session=session, event=Event(types.Content(role="user", parts=[types.Part(text=message_text)])))

        conversation_history = ""
        if session and session.events:
            # Concatenate the last few events as context
            for event in session.events:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            conversation_history += event.content.role + ": " + part.text + "\n"

        conversation_history += "User: " + message_text

        print("Conversation History: \n", conversation_history)

        # Use summarize_agent to summarize the conversation history
        summarise_agent = GenerativeModel("gemini-2.5-flash")
        summarised_message = summarise_agent.generate_content(f"Summarize this conversation: {conversation_history}")
        print("Summarised message: ", summarised_message.text)

        classify_agent = GenerativeModel("gemini-2.5-flash", system_instruction=("You are a classification agent who can classify user conversation history and route it to the appropriate agent. Focus on the last message. Categories: 'weather', 'math', 'generic'"))
        classified_message = classify_agent.generate_content(f"Classify this message and route it to the right agent: {summarised_message.text}")

        print("Selected_agent: ", classified_message.text)
        
        if "weather" in classified_message.text.lower():
            selected_agent = self.weather_agent
        elif "math" in classified_message.text.lower():
            selected_agent = self.python_agent
        else:
            selected_agent = self.generic_agent

        from google.adk.runners import Runner
        runner = Runner(
            agent=selected_agent,
            app_name=APP_NAME,
            session_service=session_service,
        )

        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=new_message):
            yield event

multi_agent_orchestrator = OrchestratorAgent(name="orchestrator", summarize_agent=summarize_agent, classify_history_agent=classify_history_agent, weather_agent=weather_agent, python_agent=python_agent, generic_agent=generic_agent)

async def second_engine(session_id: str, query: str):
    # global SESSION_ID

    existing_sessions = await session_service.list_sessions(
        app_name=APP_NAME,
        user_id=USER_ID,
    )

    session_found = False

    if existing_sessions and len(existing_sessions.sessions) > 0:
        for session in existing_sessions.sessions:
            if session.id == session_id:
                print(f"Continuing existing session: {session_id}")
                session_found = True
                
                current_session = await session_service.get_session(
                    app_name=APP_NAME,
                    user_id=USER_ID,
                    session_id=session_id
                )
                current_session.state["name"] = query
                if current_session and current_session.events:
                    print(f"Session has {len(current_session.events)} events")
                    for i, event in enumerate(current_session.events[-3:]):  # Show last 3 events
                        print(f"Event {i}: Author: {event.author}, Content: {event.content}, Actions: {event.actions}")
                
                break

    if not session_found:
        new_session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id
        )
        print(f"Created new session: {session_id}")

    content = types.Content(role='user', parts=[types.Part(text=query)])
        
    final_response_text = "Agent did not produce a final response."
    
    async for event in multi_agent_orchestrator.run_async(USER_ID, session_id, content):
        if event.is_final_response():
            if event.content and event.content.parts:
                text_parts = []
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                
                if text_parts:
                    final_response_text = ' '.join(text_parts)
                else:
                    # Fallback: if no text parts found, check if it's a function call response
                    if hasattr(event.content.parts[0], 'function_call'):
                        final_response_text = f"Function call executed: {event.content.parts[0].function_call.name}"
                    else:
                        final_response_text = "Response contains no text content."
            elif event.actions and event.actions.escalate:
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            break
    
    print(f"Response: {final_response_text}")
    return final_response_text

import uuid
import os
import requests
from urllib.parse import quote_plus

async def clean_start_engine(query: str):
    """
    Engine that starts with a fresh session to avoid conversation history issues
    """
    # Use a new session ID to avoid problematic history

    clean_session_id = f"session_{uuid.uuid4().hex[:8]}"
    
    # Create a new session
    new_session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=clean_session_id
    )
    print(f"Created clean session: {clean_session_id}")

    # Create message content
    content = types.Content(role='user', parts=[types.Part(text=query)])
    
    print(f"\n>>> User Query: {query}")
    
    final_response_text = "Agent did not produce a final response."
    
    # Use the orchestrator to route and handle the query
    async for event in multi_agent_orchestrator.run_async(USER_ID, clean_session_id, content):
        if event.is_final_response():
            if event.content and event.content.parts:
                # Extract only text parts to avoid the warning about non-text parts
                text_parts = []
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                
                if text_parts:
                    final_response_text = ' '.join(text_parts)
                else:
                    # Fallback: if no text parts found, check if it's a function call response
                    if hasattr(event.content.parts[0], 'function_call'):
                        final_response_text = f"Function call executed: {event.content.parts[0].function_call.name}"
                    else:
                        final_response_text = "Response contains no text content."
            elif event.actions and event.actions.escalate:
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            break
    
    print(f"Response: {final_response_text}")
    return final_response_text

if __name__ == "__main__":
    # asyncio.run(main_engine(query="Whats up"))
    asyncio.run(second_engine(query="whats the weather in new york"))
    # asyncio.run(second_engine(query="whats the weather in new york"))
    # asyncio.run(second_engine(query="what is this conversation about"))