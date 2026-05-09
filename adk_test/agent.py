import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent
from dotenv import load_dotenv
import io
import math
from contextlib import redirect_stdout

load_dotenv()

def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                "The weather in New York is sunny with a temperature of 25 degrees"
                " Celsius (77 degrees Fahrenheit)."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available.",
        }

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
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
import asyncio

session_service = InMemorySessionService()

APP_NAME = "weather_app"
USER_ID = "adijs"
SESSION_ID = "session_001"

async def create_session():
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    return session

async def call_agent_async(query: str, runner: Runner, user_id, session_id):
  """Sends a query to the agent and prints the final response."""
  print(f"\n>>> User Query: {query}")

  content = types.Content(role='user', parts=[types.Part(text=query)])

  final_response_text = "Agent did not produce a final response."

  async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
      if event.is_final_response():
          if event.content and event.content.parts:
             final_response_text = event.content.parts[0].text
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
    ),
    tools=[get_weather, get_current_time],
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

async def main():
    session = await create_session()

    runner = Runner(
        agent=assets_agent, # Use the router agent as the entrypoint
        app_name=APP_NAME,   # Associates runs with our app
        session_service=session_service # Uses our session manager
    )

    query = input("Enter your query: ")
    response = await call_agent_async(query, runner, USER_ID, SESSION_ID)
    code = response.strip()
    if code.startswith("```python"):
        code = code[9:]
    if code.endswith("```"):
        code = code[:-3]
            
    exec(code.strip(), globals())

if __name__ == "__main__":
    asyncio.run(main())