"""
Konfigurasi global aplikasi Progress PLSCS Meja A & B
"""
import os
import sys
from pathlib import Path

# Versi aplikasi
APP_NAME = "Progress PLSCS Meja A & B"
APP_VERSION = "1.0.0"
APP_AUTHOR = "PKL 2026"

# Direktori data aplikasi (persisten di Windows)
if getattr(sys, 'frozen', False):
    # Berjalan sebagai .exe (PyInstaller)
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Gunakan folder data pengguna yang persisten, bukan folder instalasi aplikasi.
LOCAL_APP_DATA = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
APP_DATA_ROOT = str((Path(LOCAL_APP_DATA) / 'ProgressPLSCS').resolve())
DATA_DIR = str((Path(APP_DATA_ROOT) / 'data').resolve())
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

# Path database
DB_PATH = str((Path(DATA_DIR) / 'progress_plscs.db').resolve())

# Database versi lama dipakai kembali jika tersedia agar data tidak terduplikasi.
LEGACY_DB_PATH = str((Path(APP_DATA_ROOT) / 'progress_plscs.db').resolve())
if not os.path.exists(DB_PATH) and os.path.isfile(LEGACY_DB_PATH):
    DB_PATH = LEGACY_DB_PATH

# Path backup default
BACKUP_DIR = str((Path(APP_DATA_ROOT) / 'backups').resolve())
Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
LOG_PATH = str((Path(APP_DATA_ROOT) / 'progress_plscs.log').resolve())

# Assets
ASSETS_DIR = os.path.join(APP_DIR, 'assets')

# Pengaturan default
DEFAULT_ACHIEVEMENT_THRESHOLD = 0.70  # 70%
DEFAULT_REPORT_YEAR = 2026

# Warna tema aplikasi
COLORS = {
    'primary': '#1A3A5C',        # Navy Blue
    'primary_light': '#2563EB',  # Blue
    'primary_dark': '#0F2340',   # Dark Navy
    'secondary': '#3B82F6',      # Light Blue
    'accent': '#60A5FA',         # Lighter Blue
    'surface': '#F8FAFC',        # Light Gray surface
    'surface_card': '#FFFFFF',   # White cards
    'surface_dark': '#E2E8F0',   # Medium Gray
    'text_primary': '#1E293B',   # Dark text
    'text_secondary': '#64748B', # Gray text
    'text_light': '#94A3B8',     # Light gray text
    'text_white': '#FFFFFF',     # White text
    'success': '#22C55E',        # Green - TERCAPAI
    'warning': '#F59E0B',        # Orange - perhatian
    'danger': '#EF4444',         # Red - TIDAK TERCAPAI
    'info': '#3B82F6',           # Blue - info
    'border': '#E2E8F0',         # Border light
    'sidebar_bg': '#1A3A5C',     # Sidebar background
    'sidebar_active': '#2563EB', # Active menu item
    'sidebar_hover': '#1D4ED8',  # Hover menu item
    'topbar_bg': '#FFFFFF',      # Topbar background
    'gradient_start': '#1A3A5C',
    'gradient_end': '#2563EB',
}

# Status pekerjaan
STATUS_TERCAPAI = "TERCAPAI"
STATUS_TIDAK_TERCAPAI = "TIDAK TERCAPAI"
STATUS_BELUM_DIISI = "BELUM DIISI"
STATUS_DATA_TIDAK_LENGKAP = "DATA TIDAK LENGKAP"

# Meja kerja
MEJA_A = "Meja A"
MEJA_B = "Meja B"
MEJA_OPTIONS = [MEJA_A, MEJA_B]

# Pilihan pekerjaan resmi untuk input baru. Data lama tetap dibaca apa adanya.
PEKERJAAN_OPTIONS = [
    "SCAN DOKUMEN PLSCS 2026",
    "SCAN DOKUMEN PLSCS 2025 & 2024 KEBAWAH",
]

# Ukuran jendela
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
WINDOW_MIN_WIDTH = 1024
WINDOW_MIN_HEIGHT = 600

# Sidebar width
SIDEBAR_WIDTH = 240
SIDEBAR_COLLAPSED_WIDTH = 60
