from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError


class DatabaseManager:
    def __init__(self, connection):
        """
        Initializes the database manager with a connection object containing
        credentials and connection details.
        """
        self.conn = connection
        self.engine = create_engine(self.create_connection_string(), pool_pre_ping=True)

    def create_connection_string(self):
        """
        Creates a connection string for PostgreSQL using SQLAlchemy's URL helper.
        """
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.conn.username,
            password=self.conn.password,
            host=self.conn.host,
            port=self.conn.port,
            database=self.conn.database
        )

    def get_schema_info(self):
        """
        Retrieves database schema information: table names and columns.
        """
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            columns = {table: inspector.get_columns(table) for table in tables}

            return {"tables": tables, "columns": columns}

        except SQLAlchemyError as e:
            print(f"🔥 Error retrieving schema: {e}")
            return {"error": str(e)}

    def execute_query(self, sql_query, params=None):
        """
        Executes a given SQL query and returns the results.
        Uses SQLAlchemy's `text()` for safe execution.
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql_query), params or {})
                return [dict(row) for row in result.mappings()]

        except SQLAlchemyError as e:
            print(f"🔥 Database Query Error: {e}")
            return {"error": str(e)}