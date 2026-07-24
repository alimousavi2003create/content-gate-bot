import os
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL")


@contextmanager
def get_db_cursor():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        cur = conn.cursor()
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
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        c.execute("ALTER TABLE contents ADD COLUMN IF NOT EXISTS title TEXT")
        c.execute("ALTER TABLE contents ADD COLUMN IF NOT EXISTS required_invites INTEGER DEFAULT 0")
        c.execute("""
            CREATE TABLE IF NOT EXISTS reactions (
                chat_id TEXT NOT NULL,
                message_id BIGINT NOT NULL,
                user_id TEXT NOT NULL,
                PRIMARY KEY (chat_id, message_id, user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS channel_pool (
                chat_id TEXT PRIMARY KEY,
                title TEXT,
                username TEXT,
                invite_link TEXT,
                added_at TIMESTAMP DEFAULT NOW()
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS invite_links (
                code TEXT NOT NULL,
                referrer_id TEXT NOT NULL,
                invite_link TEXT NOT NULL,
                link_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (code, referrer_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                code TEXT NOT NULL,
                referrer_id TEXT NOT NULL,
                referred_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (code, referred_id)
            )
        """)
    print("Database initialized!")
