import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL")


@contextmanager
def get_db_cursor():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db_cursor() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS contents (
                code TEXT PRIMARY KEY,
                content_type TEXT NOT NULL,
                text_content TEXT,
                file_id TEXT,
                required_chats TEXT NOT NULL,
                reaction_chat_id TEXT,
                reaction_message_id BIGINT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS reactions (
                chat_id TEXT NOT NULL,
                message_id BIGINT NOT NULL,
                user_id TEXT NOT NULL,
                PRIMARY KEY (chat_id, message_id, user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS pending_uploads (
                admin_id TEXT PRIMARY KEY,
                code TEXT,
                required_chats TEXT,
                reaction_chat_id TEXT,
                reaction_message_id BIGINT
            )
        """)
    print("Database initialized!")
