import os
import aiosqlite
from contextlib import asynccontextmanager
from typing import Optional, List, AsyncGenerator

DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vban_bridge.db')

# Ensure data directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

class Database:
    """Singleton pattern for aiosqlite connection management."""
    _connection: Optional[aiosqlite.Connection] = None

    @classmethod
    async def get_connection(cls) -> aiosqlite.Connection:
        if cls._connection is None:
            cls._connection = await aiosqlite.connect(DATABASE_PATH)
            # Enable foreign keys
            await cls._connection.execute("PRAGMA foreign_keys = ON;")
            # Enable WAL mode for better concurrent reads
            await cls._connection.execute("PRAGMA journal_mode = WAL;")
            # Return dict-like row objects
            cls._connection.row_factory = aiosqlite.Row
        return cls._connection

    @classmethod
    async def close(cls) -> None:
        if cls._connection is not None:
            await cls._connection.close()
            cls._connection = None

@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager to get the database connection."""
    conn = await Database.get_connection()
    try:
        yield conn
    except Exception as e:
        raise
    finally:
        # Since we're using a singleton connection, we don't close it here.
        pass

async def execute_query(sql: str, params: tuple = ()) -> int:
    """Execute a single query and return the last inserted row ID if applicable."""
    conn = await Database.get_connection()
    async with conn.cursor() as cursor:
        await cursor.execute(sql, params)
        await conn.commit()
        return cursor.lastrowid

async def fetch_all(sql: str, params: tuple = ()) -> List[aiosqlite.Row]:
    """Execute a query and fetch all resulting rows."""
    conn = await Database.get_connection()
    async with conn.execute(sql, params) as cursor:
        return await cursor.fetchall()

async def fetch_one(sql: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
    """Execute a query and fetch the first resulting row."""
    conn = await Database.get_connection()
    async with conn.execute(sql, params) as cursor:
        return await cursor.fetchone()
