import os
import sys
import traceback
import re
import httpx

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.sql import text  # Still imported if needed elsewhere

from .schemas import ChatRequest
from .database import DatabaseManager

# Initialize FastAPI app
app = FastAPI()

@app.get("/")  # Root endpoint for debugging
def home():
    return {"message": "API is running! Use /chat for queries."}

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:8502", "http://localhost:8503"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base URL for DeepSeek API (ensure this is correct)
BASE_URL = "http://127.0.0.1:11434/api"

def generate_sql_prompt(schema_info, question, history):
    """
    Generates an SQL query prompt based on the provided schema and user query.
    """
    prompt = f"""You are a SQL expert. Generate SQL queries based on this database schema:

Schema:
{schema_info}

Previous conversation:
{history}

Question: {question}

Output ONLY the SQL query without any explanations. Make sure to use proper JOINs and WHERE clauses as needed.
Do not enclose table names in single quotes.
Make sure the SQL syntax is correct for PostgreSQL. When counting unique values, use the syntax: COUNT(DISTINCT column_name).
"""
    return prompt

def extract_sql_query(response_text):
    """
    Extracts a valid SQL query from DeepSeek's response.

    This function searches each line for a pattern that looks like a valid SQL query
    (i.e. starting with SELECT or WITH and containing a FROM clause). If found, it
    returns that line (appending a semicolon if missing).
    """
    pattern = re.compile(
        r"^(SELECT|WITH)\s+.*\s+FROM\s+['\"]?[\w\.]+['\"]?",
        re.IGNORECASE | re.DOTALL
    )
    lines = response_text.splitlines()
    for line in lines:
        candidate = line.strip()
        if pattern.match(candidate):
            if not candidate.endswith(";"):
                candidate += ";"
            return candidate
    raise HTTPException(status_code=500, detail="DeepSeek returned an invalid SQL query.")

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint that:
      1. Connects to the database.
      2. Retrieves the schema.
      3. Generates a prompt and asks DeepSeek for an SQL query.
      4. Extracts a valid SQL query from DeepSeek's response.
      5. Executes the SQL query.
      6. Sends the query result to DeepSeek to generate a summary.
      7. Returns the SQL query, the query result, and the summary.
    """
    try:
        # Connect to the database
        db_manager = DatabaseManager(request.connection)

        # Test database connection by attempting to connect.
        try:
            with db_manager.engine.connect() as conn:
                pass  # Connection succeeded
        except Exception:
            raise HTTPException(status_code=500, detail="Database connection failed!")

        # Get schema information
        schema_info = db_manager.get_schema_info()

        # Generate SQL query prompt
        prompt = generate_sql_prompt(
            schema_info,
            request.question,
            request.chat_history
        )

        # Set a custom timeout value (300 seconds total, 60 seconds for connect, 300 for read)
        timeout = httpx.Timeout(600.0, connect=180.0, read=300.0)

        # Request SQL query from DeepSeek
        async with httpx.AsyncClient(timeout=timeout) as client:
            deepseek_response = await client.post(
                f"{BASE_URL}/generate",
                json={
                    "model": "deepseek-r1:1.5b",  # Ensure this is the correct model name
                    "prompt": prompt,
                    "stream": False
                }
            )

        # Debug: Print DeepSeek response details
        print("🔹 DeepSeek Response Status Code:", deepseek_response.status_code)
        print("🔹 DeepSeek Response Text:", deepseek_response.text)

        deepseek_response.raise_for_status()

        try:
            deepseek_data = deepseek_response.json()
        except Exception as e:
            print("🔥 JSON Parsing Failed:", str(e))
            raise HTTPException(
                status_code=500,
                detail=f"API response parsing failed: {deepseek_response.text}"
            )

        if "response" not in deepseek_data:
            raise HTTPException(status_code=500, detail="Invalid API response - missing 'response' key.")

        raw_query = deepseek_data["response"].strip()
        sql_query = extract_sql_query(raw_query)
        print("📝 Extracted SQL Query:", sql_query)

        # Execute the SQL query in the database.
        result = db_manager.execute_query(sql_query)
        print("📊 Query Result:", result)

        # Prepare a preview for the summary prompt safely.
        if isinstance(result, list):
            preview_result = result[:3]
        else:
            preview_result = result

        summary_prompt = f"Summarize these results: {str(preview_result)}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            summary_response = await client.post(
                f"{BASE_URL}/generate",
                json={
                    "model": "deepseek-r1:1.5b",
                    "prompt": summary_prompt,
                    "stream": False
                }
            )

        print("🔹 Summary Response Status Code:", summary_response.status_code)
        print("🔹 Summary Response Text:", summary_response.text)
        summary_response.raise_for_status()

        summary_data = summary_response.json()
        if "response" not in summary_data:
            raise HTTPException(status_code=500, detail="Summary generation failed - invalid response format.")

        raw_summary = summary_data["response"].strip()
        clean_summary = re.sub(r"<think>.*?</think>", "", raw_summary, flags=re.DOTALL).strip()
        summary = clean_summary if clean_summary else "Summary not available."

        return {
            "query": sql_query,
            "result": result,
            "summary": summary
        }

    except httpx.HTTPStatusError as e:
        error_msg = f"API Error: {e.response.status_code} - {e.response.text}"
        print("🔥 HTTP Error:", error_msg)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=error_msg
        )

    except httpx.ReadTimeout:
        print("🔥 ERROR: Read Timeout - API took too long to respond")
        raise HTTPException(status_code=504, detail="DeepSeek API timed out.")

    except Exception as e:
        error_details = traceback.format_exc()
        print("🔥 Critical Error:", str(e))
        print(error_details)
        raise HTTPException(
            status_code=500,
            detail=f"Processing Error: {str(e)}"
        )
