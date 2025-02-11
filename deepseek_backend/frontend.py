# frontend.py
import streamlit as st
import requests
import json
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8001"  # Update if your FastAPI runs on different port

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def display_results(response):
    """Display the SQL results in an expandable format"""
    with st.expander("View SQL Query and Results"):
        st.subheader("Generated SQL")
        st.code(response["query"], language="sql")

        st.subheader("Query Results")
        if isinstance(response["result"], list) and len(response["result"]) > 0:
            st.dataframe(response["result"], use_container_width=True)
        else:
            st.warning("No results returned from query")


def main():
    st.title("Database Chat Interface")
    st.markdown("Ask natural language questions about your database")

    # Database Connection Form
    with st.sidebar.form("db_connection"):
        st.header("Database Connection")
        db_type = st.selectbox("Database Type", ["postgresql", "mysql", "sqlite"])
        host = st.text_input("Host", "localhost")
        port = st.number_input("Port", value=5432)
        database = st.text_input("Database Name", "your-database")
        username = st.text_input("Username", "user")
        password = st.text_input("Password", type="password")

        if st.form_submit_button("Connect"):
            st.session_state.connection = {
                "db_type": db_type,
                "host": host,
                "port": port,
                "database": database,
                "username": username,
                "password": password
            }
            st.success("Connection parameters saved!")

    # Main Chat Interface
    if "connection" not in st.session_state:
        st.warning("Please configure database connection in the sidebar")
        return

    user_question = st.chat_input("Ask your database question...")

    if user_question:
        # Add user question to history
        st.session_state.chat_history.append({
            "type": "user",
            "content": user_question,
            "timestamp": datetime.now().isoformat()
        })

        # Prepare API request
        payload = {
            "question": user_question,
            "connection": st.session_state.connection,
            "chat_history": [msg["content"] for msg in st.session_state.chat_history if msg["type"] == "user"]
        }

        try:
            # Show loading spinner
            with st.spinner("Analyzing your question..."):
                response = requests.post(
                    f"{BACKEND_URL}/chat",
                    json=payload,
                    timeout=600
                )

            if response.status_code == 200:
                result = response.json()

                # Add assistant response to history
                st.session_state.chat_history.append({
                    "type": "assistant",
                    "content": result["summary"],
                    "query": result["query"],
                    "result": result["result"],
                    "timestamp": datetime.now().isoformat()
                })

                # Display latest response
                latest = st.session_state.chat_history[-1]
                with st.chat_message("assistant"):
                    st.markdown(latest["content"])
                    display_results(latest)

            else:
                st.error(f"API Error: {response.text}")

        except requests.exceptions.RequestException as e:
            st.error(f"Connection failed: {str(e)}")

    # Display chat history
    for msg in st.session_state.chat_history:
        if msg["type"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])
                display_results(msg)


if __name__ == "__main__":
    main()