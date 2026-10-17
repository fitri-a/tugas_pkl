"""Backup dan restore database SQLite secara aman."""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from app.config import DB_PATH, BACKUP_DIR
from app.database.connection import close_connection, execute_query

logger = logging.getLogger(__name__)


def get_backup_dir() -> Path:
    """Mengambil folder backup aktif; hanya path absolut yang digunakan."""
    try:
        row = execute_query("SELECT value FROM settings WHERE key='backup_dir'", fetch='one')
        configured = (row['value'] or '').strip() if row else ''
    except sqlite3.Error:
        configured = ''
    folder = Path(configured).expanduser() if configured else Path(BACKUP_DIR)
    if not folder.is_absolute():
        logger.warning('backup_dir relatif diabaikan: %s', configured)
        folder = Path(BACKUP_DIR)
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def backup_database(filepath: str | None = None) -> str:
    target = Path(filepath).expanduser().resolve() if filepath else get_backup_dir() / f"progress_plscs_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    source_path = Path(DB_PATH).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f'Database utama tidak ditemukan: {source_path}')
    if target == source_path:
        raise ValueError('Lokasi backup tidak boleh sama dengan database utama.')
    source = sqlite3.connect(str(source_path))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
        check = destination.execute("PRAGMA integrity_check").fetchone()[0]
        if check != 'ok':
            raise sqlite3.DatabaseError(f'Validasi backup gagal: {check}')
        destination.commit()
        if not target.is_file() or target.stat().st_size <= 0 or not validate_backup(str(target)):
            raise sqlite3.DatabaseError('File backup tidak ada, kosong, atau bukan database Progress PLSCS yang valid.')
        actual_path = str(target)
        execute_query("INSERT INTO backup_log(filepath, tipe, status, keterangan) VALUES (?, 'backup', 'sukses', ?)", (actual_path, f'Backup SQLite berhasil ({target.stat().st_size} byte)'))
        logger.info('Backup berhasil: %s (%d byte)', actual_path, target.stat().st_size)
        return actual_path
    except Exception as exc:
        logger.exception('Backup gagal ke %s', target)
        try:
            execute_query("INSERT INTO backup_log(filepath, tipe, status, keterangan) VALUES (?, 'backup', 'gagal', ?)", (str(target), str(exc)))
        except sqlite3.Error:
            logger.exception('Gagal mencatat kegagalan backup ke backup_log')
        raise
    finally:
        destination.close()
        source.close()


def validate_backup(filepath: str) -> bool:
    path = Path(filepath).expanduser().resolve()
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and bool(
            conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='progress'").fetchone()
        )
    finally:
        conn.close()


def restore_database(filepath: str) -> None:
    if not validate_backup(filepath):
        raise ValueError("File backup tidak valid atau bukan database Progress PLSCS.")
    safety = backup_database()
    close_connection()
    source = sqlite3.connect(str(Path(filepath).expanduser().resolve()))
    destination = sqlite3.connect(str(Path(DB_PATH).resolve()))
    restore_error = None
    try:
        source.backup(destination)
        destination.commit()
    except Exception as exc:
        restore_error = exc
    finally:
        destination.close()
        source.close()
    if restore_error is not None:
        # Pulihkan database aktif dari backup pengaman jika restore gagal sebagian.
        rollback_source = sqlite3.connect(str(Path(safety).resolve()))
        rollback_destination = sqlite3.connect(str(Path(DB_PATH).resolve()))
        try:
            rollback_source.backup(rollback_destination)
            rollback_destination.commit()
            execute_query("INSERT INTO backup_log(filepath, tipe, status, keterangan) VALUES (?, 'restore', 'gagal', ?)", (str(Path(filepath).resolve()), str(restore_error)))
        finally:
            rollback_destination.close()
            rollback_source.close()
            raise restore_error
    execute_query("INSERT INTO backup_log(filepath, tipe, status, keterangan) VALUES (?, 'restore', 'sukses', ?)", (str(Path(filepath).resolve()), f'Dipulihkan; pengaman: {safety}'))
