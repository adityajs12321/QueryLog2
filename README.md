# QueryLog: AI-Powered Logfile Assistant

QueryLog is an intelligent log analysis engine that allows users to query structured and unstructured system logs using Generative AI. Powered by **Google Gemini** and orchestrated using **LangGraph**, the application translates natural enquiries into executable **PostgreSQL** queries, executing them against parsed unstructured log tables, and preserving conversational memory context over RESTful APIs.

## Key Features

- **Natural Language to SQL Generation**: Automatically parses human questions (e.g., "What time did natalierivera create an account?") directly into complex SQL search queries using similarity and vector comparisons.
- **LangGraph Agentic Routing**: Intelligently classifies prompts into database-related log queries (`sql_agent`) or general conversational inquiries (`generic_agent`), streamlining LLM token usage and responses.
- **RESTful API**: Exposes endpoints via **FastAPI** to facilitate querying by `conversation_id`, preserving chat history for coherent, multi-turn diagnostic sessions.
- **Automated ETL Pipelines**: Extracts data from standard log formats (like XML event logs), and includes utilities for MongoDB to PostgreSQL data migration.
- **Semantic/Fuzzy Search**: Integrates `similarity` thresholding (`pg_trgm`) and PostgreSQL database text search capabilities to find matching log events even with imprecise queries.
- **LLM Observability**: Uses **Langfuse** callbacks to trace agent workflows and monitor performance.

## Project Architecture

- `interface.py` - The FastAPI entry point exposing `/query` endpoints for interaction with the agent.
- `query_engine_v2.py` - The main advanced logic engine utilizing `langgraph` and `langchain` models. Defines the state graph, the SQL generation prompts, and manages PostgreSQL interaction.
- `query_engine.py` - The legacy inference engine mapping direct Gemini prompts to JSON-enforced SQL generation.
- `Utils/` - Helper modules for Databases & ETL:
  - `ETL.py`: Extracts and parses raw XML logs.
  - `postgre.py`: Handles PostgreSQL connection, table creation, insertion, and fetching chat history.
  - `mongo.py`: MongoDB interaction logic.

## Setup & Installation

**1. Prerequisites**
* Python 3.10+
* A running instance of PostgreSQL
* An active Google Gemini / VertexAI API Key

**2. Clone and prepare your environment:**
```bash
git clone <your-repo-url>
cd QueryLog2
python -m venv query_log
source query_log/bin/activate
```

**3. Install Dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configuration:**
Create a `.env` file in the root directory with the necessary API keys and database credentials:
```env
GEMINI_API_KEY="your_google_gemini_api_key"
# Add your local PostgreSQL connection strings appropriately as required by `Utils/postgre.py`
```
*(Optional)* Add a `gv.json` inside the workspace root if using Google Cloud Application Credentials for Vertex AI models.

## Usage

**Running the API Server**
Start the FastAPI server via Uvicorn:
```bash
uvicorn interface:app --reload
```

**Making Queries**
You can use `curl`, Postman, or a Python script to interact with the assistant:
```bash
curl -X POST "http://127.0.0.1:8000/query?conversation_id=1&query=Who%20was%20removed%20from%20the%20security%20enabled%20local%20group"
```

The system will route the query, formulate a similarity-based Postgres SQL statement, attempt execution, and return log records. If no direct match is found, the engine implements a graceful score-reduction feedback loops (`min_score`) to return the closest contextual logs.

## Technologies Used
* **FastAPI**: Backend Web Framework
* **LangGraph & LangChain**: Agentic workflows & orchestration
* **Google Gemini 2.5**: LLM Foundation
* **PostgreSQL (psycopg2)**: Relational Data & Semantic text search
* **Langfuse**: Tracing and LLM analytics