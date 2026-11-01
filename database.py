import os
import sqlite3
from flask import g
import psycopg2
from psycopg2.extras import DictCursor


def get_database_url():
    """Returns cleaned DATABASE_URL from environment or None."""
    url = os.getenv("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        # Fix for platforms (e.g. Render/Heroku) using legacy postgres:// prefix
        url = url.replace("postgres://", "postgresql://", 1)
    return url or None


def get_db_path():
    """Returns local SQLite database file path."""
    return os.getenv("DATABASE_PATH", "job_tracker.db")


class PostgresCursorWrapper:
    """Wraps psycopg2 cursor for consistent dict and tuple access."""
    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @property
    def lastrowid(self):
        return getattr(self.cursor, "lastrowid", None)


class PostgresConnectionWrapper:
    """Wraps psycopg2 connection to auto-translate '?' placeholders to '%s'."""
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        # Automatically translate SQLite ? placeholders to PostgreSQL %s
        sql = sql.replace("?", "%s")
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return PostgresCursorWrapper(cursor)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def get_connection():
    """Returns a standalone database connection (supports both SQLite and PostgreSQL)."""
    db_url = get_database_url()
    if db_url:
        conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
        return PostgresConnectionWrapper(conn)
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def get_db():
    """Returns the database connection for the current Flask request context."""
    if "db" not in g:
        g.db = get_connection()
    return g.db


def close_db(e=None):
    """Closes the request database connection."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initializes the database schema for either PostgreSQL or SQLite."""
    db_url = get_database_url()
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()

    if db_url:
        # Convert SQLite autoincrement syntax to PostgreSQL serial syntax
        pg_schema = schema.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cursor:
            cursor.execute(pg_schema)
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(get_db_path())
        conn.executescript(schema)
        conn.commit()
        conn.close()
