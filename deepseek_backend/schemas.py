from pydantic import BaseModel, Field
from typing import List

class DatabaseConnection(BaseModel):
    db_type: str  # e.g., "postgresql", "mysql"
    host: str
    port: int
    database: str
    username: str
    password: str

class ChatRequest(BaseModel):
    question: str
    connection: DatabaseConnection
    chat_history: List[str] = Field(default_factory=list)

# Example usage:
chat_req = ChatRequest(
    question="How do I connect?",
    connection=DatabaseConnection(
        db_type="postgresql", host="localhost", port=5432,
        database="example_db", username="user", password="pass"
    )
)
print(chat_req.chat_history)  # Prints: []
