"""
Koneksi database SQLite
"""
import sqlite3
import threading
import logging
from app.config import DB_PATH

logger = logging.getLogger(__name__)

# Thread-local storage untuk koneksi per-thread
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Mendapatkan koneksi database thread-safe."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
    return _local.conn


def close_connection():
    """Menutup koneksi database thread saat ini."""
    if hasattr(_local, 'conn') and _local.conn:
        _local.conn.close()
        _local.conn = None


def execute_query(query: str, params: tuple = (), fetch: str = None):
    """
    Menjalankan query dengan parameter.
    fetch: None, 'one', 'all'
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch == 'one':
            return cursor.fetchone()
        elif fetch == 'all':
            return cursor.fetchall()
        else:
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Database error: {e}\nQuery: {query}\nParams: {params}")
        raise


def execute_many(query: str, params_list: list):
    """Menjalankan query dengan banyak parameter (batch insert)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Database batch error: {e}")
        raise


def run_migrations():
    """Kompatibilitas API: jalankan migrasi terpusat."""
    from app.database.migrations import run_migrations as migrate
    return migrate()


def transaction(func):
    """Decorator untuk operasi dalam satu transaksi."""
    def wrapper(*args, **kwargs):
        conn = get_connection()
        try:
            result = func(*args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction error: {e}")
            raise
    return wrapper
