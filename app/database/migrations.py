"""
Migrasi database - membuat tabel dan skema
"""
import logging
from app.database.connection import get_connection
from app.config import DEFAULT_ACHIEVEMENT_THRESHOLD, DEFAULT_REPORT_YEAR

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2


def run_migrations():
    """Menjalankan semua migrasi database."""
    conn = get_connection()
    _create_tables(conn)
    _seed_defaults(conn)
    logger.info("Database migrations completed successfully.")


def _create_tables(conn):
    """Membuat tabel jika belum ada."""
    conn.executescript("""
        -- Tabel PIC (Person In Charge)
        CREATE TABLE IF NOT EXISTS pic (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nama        TEXT NOT NULL UNIQUE COLLATE NOCASE,
            aktif       INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        -- Tabel Progress Harian
        CREATE TABLE IF NOT EXISTS progress (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal             TEXT NOT NULL,        -- ISO format: YYYY-MM-DD
            meja                TEXT NOT NULL,        -- 'Meja A' atau 'Meja B'
            nama_pic            TEXT NOT NULL,        -- Nama PIC (bisa beberapa, pisah &)
            pekerjaan           TEXT NOT NULL,
            rincian_pengerjaan  TEXT,
            target              REAL,
            realisasi           REAL,
            keterangan          TEXT,
            imported_from       TEXT,                 -- Nama file Excel jika diimpor
            created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        -- Index untuk performa query
        CREATE INDEX IF NOT EXISTS idx_progress_tanggal ON progress(tanggal);
        CREATE INDEX IF NOT EXISTS idx_progress_meja ON progress(meja);
        CREATE INDEX IF NOT EXISTS idx_progress_pic ON progress(nama_pic);
        CREATE INDEX IF NOT EXISTS idx_progress_tanggal_meja ON progress(tanggal, meja);

        -- Tabel Pengaturan Aplikasi
        CREATE TABLE IF NOT EXISTS settings (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        -- Tabel Log Backup
        CREATE TABLE IF NOT EXISTS backup_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath    TEXT NOT NULL,
            tipe        TEXT NOT NULL,   -- 'backup' atau 'restore'
            status      TEXT NOT NULL,   -- 'sukses' atau 'gagal'
            keterangan  TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)
    # Migrasi aditif untuk database lama yang mungkin hanya memiliki sebagian kolom.
    required = {
        'progress': {
            'rincian_pengerjaan': 'TEXT', 'target': 'REAL', 'realisasi': 'REAL',
            'keterangan': 'TEXT', 'imported_from': 'TEXT',
            'created_at': "TEXT NOT NULL DEFAULT ''",
            'updated_at': "TEXT NOT NULL DEFAULT ''",
        },
        'settings': {'updated_at': "TEXT NOT NULL DEFAULT ''"},
    }
    for table, columns in required.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    conn.commit()
    logger.info("Tables created/verified.")


def _seed_defaults(conn):
    """Mengisi nilai default untuk pengaturan."""
    defaults = {
        'achievement_threshold': str(DEFAULT_ACHIEVEMENT_THRESHOLD),
        'report_year': str(DEFAULT_REPORT_YEAR),
        'backup_dir': '',
        'theme': 'light',
        'rows_per_page': '25',
        'date_format': 'DD/MM/YYYY',
            'schema_version': str(SCHEMA_VERSION),
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
    conn.commit()
    logger.info("Default settings seeded.")
