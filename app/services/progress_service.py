"""
Service untuk operasi CRUD Progress dan PIC
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from app.database.connection import execute_query, execute_many, get_connection
from app.database.models import Progress, PIC, Settings, RekapHarian, RekapMingguan, RekapBulanan
from app.config import (
    STATUS_TERCAPAI, STATUS_TIDAK_TERCAPAI, STATUS_BELUM_DIISI,
    STATUS_DATA_TIDAK_LENGKAP, MEJA_A, MEJA_B
)

logger = logging.getLogger(__name__)

NAMA_BULAN = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
    5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
    9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
}


# ============================================================
# PENGATURAN
# ============================================================

def get_settings() -> Settings:
    """Mengambil semua pengaturan dari database."""
    rows = execute_query("SELECT key, value FROM settings", fetch='all')
    d = {r['key']: r['value'] for r in rows} if rows else {}
    return Settings(
        achievement_threshold=float(d.get('achievement_threshold', 0.70)),
        report_year=int(d.get('report_year', 2026)),
        backup_dir=d.get('backup_dir', ''),
        theme=d.get('theme', 'light'),
        rows_per_page=int(d.get('rows_per_page', 25)),
        date_format=d.get('date_format', 'DD/MM/YYYY'),
    )


def save_setting(key: str, value: str):
    """Menyimpan satu pengaturan."""
    execute_query(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))",
        (key, value)
    )


def get_threshold_pct() -> float:
    """Mengambil threshold pencapaian dalam persen (0-100)."""
    s = get_settings()
    return s.achievement_threshold * 100


# ============================================================
# PIC
# ============================================================

def get_all_pic(aktif_only: bool = False) -> List[PIC]:
    """Mengambil semua PIC."""
    if aktif_only:
        rows = execute_query("SELECT * FROM pic WHERE aktif=1 ORDER BY nama", fetch='all')
    else:
        rows = execute_query("SELECT * FROM pic ORDER BY aktif DESC, nama", fetch='all')
    return [PIC(id=r['id'], nama=r['nama'], aktif=bool(r['aktif']),
                created_at=r['created_at'], updated_at=r['updated_at']) for r in rows] if rows else []


def add_pic(nama: str) -> int:
    """Menambah PIC baru. Return ID."""
    nama = nama.strip()
    if not nama:
        raise ValueError("Nama PIC tidak boleh kosong.")
    existing = execute_query("SELECT id FROM pic WHERE nama=? COLLATE NOCASE", (nama,), fetch='one')
    if existing:
        raise ValueError(f"PIC '{nama}' sudah ada.")
    return execute_query(
        "INSERT INTO pic (nama, aktif) VALUES (?, 1)",
        (nama,)
    )


def update_pic(pic_id: int, nama: str):
    """Mengupdate nama PIC."""
    nama = nama.strip()
    if not nama:
        raise ValueError("Nama PIC tidak boleh kosong.")
    execute_query(
        "UPDATE pic SET nama=?, updated_at=datetime('now','localtime') WHERE id=?",
        (nama, pic_id)
    )


def toggle_pic_aktif(pic_id: int, aktif: bool):
    """Mengaktifkan atau menonaktifkan PIC."""
    execute_query(
        "UPDATE pic SET aktif=?, updated_at=datetime('now','localtime') WHERE id=?",
        (1 if aktif else 0, pic_id)
    )


def get_pic_names(aktif_only: bool = True) -> List[str]:
    """Mengambil daftar nama PIC saja."""
    pics = get_all_pic(aktif_only=aktif_only)
    return [p.nama for p in pics]


def ensure_pic_exists(nama_pic: str):
    """Memastikan PIC ada, jika tidak buat baru (untuk proses import)."""
    for nama in _split_pic(nama_pic):
        nama = nama.strip()
        if nama:
            try:
                add_pic(nama)
            except ValueError:
                pass  # Sudah ada


def _split_pic(nama_pic: str) -> List[str]:
    """Memisahkan nama PIC yang dipisahkan &."""
    return [n.strip() for n in nama_pic.replace('&', ',').split(',') if n.strip()]


# ============================================================
# PROGRESS CRUD
# ============================================================

def add_progress(p: Progress) -> int:
    """Menambah data progress baru. Return ID."""
    _validate_progress(p)
    return execute_query(
        """INSERT INTO progress
           (tanggal, meja, nama_pic, pekerjaan, rincian_pengerjaan, target, realisasi, keterangan, imported_from)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (p.tanggal, p.meja, p.nama_pic, p.pekerjaan, p.rincian_pengerjaan or '',
         p.target, p.realisasi, p.keterangan or '', p.imported_from or '')
    )


def update_progress(p: Progress):
    """Mengupdate data progress yang sudah ada."""
    _validate_progress(p)
    execute_query(
        """UPDATE progress SET
           tanggal=?, meja=?, nama_pic=?, pekerjaan=?, rincian_pengerjaan=?,
           target=?, realisasi=?, keterangan=?, updated_at=datetime('now','localtime')
           WHERE id=?""",
        (p.tanggal, p.meja, p.nama_pic, p.pekerjaan, p.rincian_pengerjaan or '',
         p.target, p.realisasi, p.keterangan or '', p.id)
    )


def delete_progress(progress_id: int):
    """Menghapus data progress berdasarkan ID."""
    execute_query("DELETE FROM progress WHERE id=?", (progress_id,))


def get_progress_by_id(progress_id: int) -> Optional[Progress]:
    """Mengambil satu record progress berdasarkan ID."""
    row = execute_query("SELECT * FROM progress WHERE id=?", (progress_id,), fetch='one')
    return _row_to_progress(row) if row else None


def get_progress(
    meja: str = None,
    tanggal_mulai: str = None,
    tanggal_selesai: str = None,
    nama_pic: str = None,
    pekerjaan: str = None,
    keyword: str = None,
    tahun: int = None,
    status: str = None,
    limit: int = None,
    offset: int = 0,
    order_by: str = 'tanggal DESC, id DESC'
) -> List[Progress]:
    """Mengambil data progress dengan filter opsional."""
    conditions = []
    params = []

    if meja:
        conditions.append("meja=?")
        params.append(meja)
    if tanggal_mulai:
        conditions.append("tanggal>=?")
        params.append(tanggal_mulai)
    if tanggal_selesai:
        conditions.append("tanggal<=?")
        params.append(tanggal_selesai)
    if nama_pic:
        conditions.append("nama_pic LIKE ?")
        params.append(f"%{nama_pic}%")
    if pekerjaan:
        conditions.append("pekerjaan LIKE ?")
        params.append(f"%{pekerjaan}%")
    if keyword:
        conditions.append("(pekerjaan LIKE ? OR rincian_pengerjaan LIKE ? OR nama_pic LIKE ? OR keterangan LIKE ?)")
        params.extend([f"%{keyword}%"] * 4)
    if tahun:
        conditions.append("strftime('%Y', tanggal)=?")
        params.append(str(tahun))
    if status:
        threshold = get_threshold_pct()
        if status == STATUS_TERCAPAI:
            conditions.append("realisasi IS NOT NULL AND target > 0 AND (CAST(realisasi AS REAL)/target*100) >= ?")
            params.append(threshold)
        elif status == STATUS_TIDAK_TERCAPAI:
            conditions.append("((realisasi IS NOT NULL AND target > 0 AND (CAST(realisasi AS REAL)/target*100) < ?) OR target IS NULL OR target <= 0 OR realisasi IS NULL)")
            params.append(threshold)
        elif status in (STATUS_DATA_TIDAK_LENGKAP, STATUS_BELUM_DIISI):
            conditions.append("((target IS NULL OR target <= 0) OR realisasi IS NULL)")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM progress {where} ORDER BY {order_by}"

    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"

    rows = execute_query(query, tuple(params), fetch='all')
    return [_row_to_progress(r) for r in rows] if rows else []


def count_progress(
    meja: str = None,
    tanggal_mulai: str = None,
    tanggal_selesai: str = None,
    nama_pic: str = None,
    pekerjaan: str = None,
    keyword: str = None,
    tahun: int = None,
    status: str = None,
) -> int:
    """Menghitung jumlah record progress dengan filter."""
    conditions = []
    params = []

    if meja:
        conditions.append("meja=?")
        params.append(meja)
    if tanggal_mulai:
        conditions.append("tanggal>=?")
        params.append(tanggal_mulai)
    if tanggal_selesai:
        conditions.append("tanggal<=?")
        params.append(tanggal_selesai)
    if nama_pic:
        conditions.append("nama_pic LIKE ?")
        params.append(f"%{nama_pic}%")
    if pekerjaan:
        conditions.append("pekerjaan LIKE ?")
        params.append(f"%{pekerjaan}%")
    if keyword:
        conditions.append("(pekerjaan LIKE ? OR rincian_pengerjaan LIKE ? OR nama_pic LIKE ? OR keterangan LIKE ?)")
        params.extend([f"%{keyword}%"] * 4)
    if tahun:
        conditions.append("strftime('%Y', tanggal)=?"); params.append(str(tahun))
    if status:
        threshold = get_threshold_pct()
        if status == STATUS_TERCAPAI:
            conditions.append("realisasi IS NOT NULL AND target > 0 AND (CAST(realisasi AS REAL)/target*100) >= ?"); params.append(threshold)
        elif status == STATUS_TIDAK_TERCAPAI:
            conditions.append("((realisasi IS NOT NULL AND target > 0 AND (CAST(realisasi AS REAL)/target*100) < ?) OR target IS NULL OR target <= 0 OR realisasi IS NULL)"); params.append(threshold)
        elif status in (STATUS_DATA_TIDAK_LENGKAP, STATUS_BELUM_DIISI):
            conditions.append("((target IS NULL OR target <= 0) OR realisasi IS NULL)")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    row = execute_query(f"SELECT COUNT(*) as cnt FROM progress {where}", tuple(params), fetch='one')
    return row['cnt'] if row else 0


def check_duplicate(tanggal: str, meja: str, nama_pic: str, pekerjaan: str, exclude_id: int = None) -> bool:
    """Mengecek apakah data progress sudah ada (potensi duplikat)."""
    query = """SELECT COUNT(*) as cnt FROM progress
               WHERE tanggal=? AND meja=? AND nama_pic=? AND pekerjaan=?"""
    params = [tanggal, meja, nama_pic, pekerjaan]
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
    row = execute_query(query, tuple(params), fetch='one')
    return (row['cnt'] > 0) if row else False


# ============================================================
# STATISTIK & REKAP
# ============================================================

def get_dashboard_stats(tahun: int = None, meja: str = None, tanggal_mulai: str = None,
                        tanggal_selesai: str = None, nama_pic: str = None,
                        pekerjaan: str = None) -> Dict[str, Any]:
    """Mengambil statistik ringkasan untuk dashboard."""
    conditions = []
    params = []
    if tahun:
        conditions.append("strftime('%Y', tanggal) = ?")
        params.append(str(tahun))
    if meja:
        conditions.append("meja = ?")
        params.append(meja)
    if tanggal_mulai:
        conditions.append("tanggal >= ?")
        params.append(tanggal_mulai)
    if tanggal_selesai:
        conditions.append("tanggal <= ?")
        params.append(tanggal_selesai)
    if nama_pic:
        conditions.append("nama_pic LIKE ?")
        params.append(f"%{nama_pic}%")
    if pekerjaan:
        conditions.append("pekerjaan LIKE ?")
        params.append(f"%{pekerjaan}%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    threshold = get_threshold_pct()

    query = f"""
        SELECT
            COUNT(*) as total_entri,
            COALESCE(SUM(target), 0) as total_target,
            COALESCE(SUM(CASE WHEN realisasi IS NOT NULL THEN realisasi ELSE 0 END), 0) as total_realisasi,
            COUNT(CASE WHEN realisasi IS NOT NULL AND target > 0
                       AND (CAST(realisasi AS REAL)/target*100) >= {threshold} THEN 1 END) as jumlah_tercapai,
            COUNT(CASE WHEN realisasi IS NOT NULL AND target > 0
                       AND (CAST(realisasi AS REAL)/target*100) < {threshold} THEN 1 END) as jumlah_tidak_tercapai,
            COUNT(CASE WHEN realisasi IS NULL AND target > 0 THEN 1 END) as jumlah_belum_diisi,
            COUNT(CASE WHEN target IS NULL OR target <= 0 OR nama_pic IS NULL OR pekerjaan IS NULL THEN 1 END) as jumlah_tidak_lengkap
        FROM progress {where}
    """
    row = execute_query(query, tuple(params), fetch='one')
    if not row:
        return {}

    total_target = row['total_target'] or 0
    total_realisasi = row['total_realisasi'] or 0
    pct = (total_realisasi / total_target * 100) if total_target > 0 else 0

    return {
        'total_entri': row['total_entri'],
        'total_target': total_target,
        'total_realisasi': total_realisasi,
        'persentase_keseluruhan': pct,
        'jumlah_tercapai': row['jumlah_tercapai'],
        'jumlah_tidak_tercapai': row['jumlah_tidak_tercapai'],
        'jumlah_belum_diisi': row['jumlah_belum_diisi'],
        'jumlah_tidak_lengkap': row['jumlah_tidak_lengkap'],
    }


def get_dashboard_status_counts(**filters) -> Dict[str, int]:
    """Mengambil jumlah status dengan filter dashboard yang sama."""
    conditions, params = _dashboard_conditions(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    threshold = get_threshold_pct()
    row = execute_query(f"""
        SELECT
          COUNT(CASE WHEN realisasi IS NOT NULL AND target > 0 AND realisasi / target * 100 >= ? THEN 1 END) AS selesai,
          COUNT(CASE WHEN realisasi IS NOT NULL AND target > 0 AND realisasi / target * 100 < ? THEN 1 END) AS proses,
          COUNT(CASE WHEN realisasi IS NULL AND target > 0 THEN 1 END) AS belum_diisi,
          COUNT(CASE WHEN target IS NULL OR target <= 0 OR nama_pic IS NULL OR pekerjaan IS NULL THEN 1 END) AS tidak_lengkap
        FROM progress {where}
    """, (threshold, threshold, *params), fetch='one')
    return {key: int(row[key] or 0) for key in ('selesai', 'proses', 'belum_diisi', 'tidak_lengkap')}


def get_dashboard_period_data(period: str = 'monthly', **filters) -> List[Dict[str, Any]]:
    """Agregasi target/realisasi untuk grafik dashboard."""
    expressions = {
        'daily': ("tanggal", "tanggal"),
        'weekly': ("strftime('%Y-W%W', tanggal)", "strftime('%Y-W%W', tanggal)"),
        'monthly': ("strftime('%Y-%m', tanggal)", "strftime('%Y-%m', tanggal)"),
        'yearly': ("strftime('%Y', tanggal)", "strftime('%Y', tanggal)"),
    }
    expression, label_expression = expressions.get(period, expressions['monthly'])
    conditions, params = _dashboard_conditions(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = execute_query(f"""
        SELECT {label_expression} AS periode, COALESCE(SUM(target), 0) AS target,
               COALESCE(SUM(realisasi), 0) AS realisasi, COUNT(*) AS jumlah
        FROM progress {where}
        GROUP BY {expression} ORDER BY {expression}
    """, tuple(params), fetch='all')
    return [dict(row) for row in rows] if rows else []


def get_dashboard_pic_data(**filters) -> List[Dict[str, Any]]:
    """Agregasi pekerjaan per PIC, dibatasi lima PIC terbanyak."""
    conditions, params = _dashboard_conditions(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = execute_query(f"""
        SELECT nama_pic, COUNT(*) AS jumlah, COALESCE(SUM(target), 0) AS target,
               COALESCE(SUM(realisasi), 0) AS realisasi
        FROM progress {where}
        GROUP BY nama_pic ORDER BY jumlah DESC, nama_pic LIMIT 5
    """, tuple(params), fetch='all')
    return [dict(row) for row in rows] if rows else []


def _dashboard_conditions(filters: Dict[str, Any]):
    conditions, params = [], []
    if filters.get('tahun'):
        conditions.append("strftime('%Y', tanggal) = ?")
        params.append(str(filters['tahun']))
    for field in ('meja',):
        if filters.get(field):
            conditions.append(f"{field} = ?")
            params.append(filters[field])
    for field in ('tanggal_mulai', 'tanggal_selesai'):
        if filters.get(field):
            operator = '>=' if field == 'tanggal_mulai' else '<='
            conditions.append(f"tanggal {operator} ?")
            params.append(filters[field])
    for field in ('nama_pic', 'pekerjaan'):
        if filters.get(field):
            conditions.append(f"{field} LIKE ?")
            params.append(f"%{filters[field]}%")
    return conditions, params


def get_daily_chart_data(tahun: int, bulan: int = None, meja: str = None) -> List[Dict]:
    """Data untuk grafik progress harian."""
    conditions = ["strftime('%Y', tanggal) = ?"]
    params = [str(tahun)]
    if bulan:
        conditions.append("strftime('%m', tanggal) = ?")
        params.append(f"{bulan:02d}")
    if meja:
        conditions.append("meja = ?")
        params.append(meja)

    where = f"WHERE {' AND '.join(conditions)}"
    rows = execute_query(
        f"""SELECT tanggal,
                   COALESCE(SUM(target), 0) as total_target,
                   COALESCE(SUM(realisasi), 0) as total_realisasi,
                   meja
            FROM progress {where}
            GROUP BY tanggal, meja
            ORDER BY tanggal""",
        tuple(params), fetch='all'
    )
    return [dict(r) for r in rows] if rows else []


def get_monthly_chart_data(tahun: int, meja: str = None) -> List[Dict]:
    """Data untuk grafik progress bulanan."""
    conditions = ["strftime('%Y', tanggal) = ?"]
    params = [str(tahun)]
    if meja:
        conditions.append("meja = ?")
        params.append(meja)

    where = f"WHERE {' AND '.join(conditions)}"
    rows = execute_query(
        f"""SELECT strftime('%m', tanggal) as bulan_num,
                   COALESCE(SUM(target), 0) as total_target,
                   COALESCE(SUM(realisasi), 0) as total_realisasi,
                   meja
            FROM progress {where}
            GROUP BY bulan_num, meja
            ORDER BY bulan_num""",
        tuple(params), fetch='all'
    )
    result = []
    for r in (rows or []):
        d = dict(r)
        d['nama_bulan'] = NAMA_BULAN.get(int(d['bulan_num']), d['bulan_num'])
        result.append(d)
    return result


def get_rekap_harian(tanggal: str, meja: str = None) -> List[Dict]:
    """Rekap data harian untuk satu tanggal."""
    conditions = ["tanggal = ?"]
    params = [tanggal]
    if meja:
        conditions.append("meja = ?")
        params.append(meja)

    where = f"WHERE {' AND '.join(conditions)}"
    rows = execute_query(
        f"SELECT * FROM progress {where} ORDER BY meja, nama_pic",
        tuple(params), fetch='all'
    )
    return [dict(r) for r in rows] if rows else []


def get_rekap_mingguan(tanggal_mulai: str, tanggal_selesai: str, meja: str = None) -> List[Dict]:
    """Rekap mingguan berdasarkan rentang tanggal."""
    conditions = ["tanggal >= ?", "tanggal <= ?"]
    params = [tanggal_mulai, tanggal_selesai]
    if meja:
        conditions.append("meja = ?")
        params.append(meja)

    where = f"WHERE {' AND '.join(conditions)}"
    rows = execute_query(
        f"""SELECT meja, nama_pic, pekerjaan,
                   COUNT(*) as jumlah_hari,
                   COALESCE(SUM(target), 0) as total_target,
                   COALESCE(SUM(realisasi), 0) as total_realisasi
            FROM progress {where}
            GROUP BY meja, pekerjaan
            ORDER BY meja, pekerjaan""",
        tuple(params), fetch='all'
    )
    return [dict(r) for r in rows] if rows else []


def get_rekap_bulanan(tahun: int, bulan: int, meja: str = None) -> List[Dict]:
    """Rekap bulanan berdasarkan tahun dan bulan."""
    conditions = ["strftime('%Y', tanggal) = ?", "strftime('%m', tanggal) = ?"]
    params = [str(tahun), f"{bulan:02d}"]
    if meja:
        conditions.append("meja = ?")
        params.append(meja)

    where = f"WHERE {' AND '.join(conditions)}"
    rows = execute_query(
        f"""SELECT meja, pekerjaan,
                   COUNT(*) as jumlah_hari,
                   COALESCE(SUM(target), 0) as total_target,
                   COALESCE(SUM(realisasi), 0) as total_realisasi,
                   GROUP_CONCAT(DISTINCT nama_pic) as semua_pic
            FROM progress {where}
            GROUP BY meja, pekerjaan
            ORDER BY meja, pekerjaan""",
        tuple(params), fetch='all'
    )
    result = []
    for r in (rows or []):
        d = dict(r)
        d['nama_bulan'] = NAMA_BULAN.get(bulan, '')
        d['tahun'] = tahun
        d['persentase'] = (d['total_realisasi'] / d['total_target'] * 100
                           if d['total_target'] > 0 else 0)
        result.append(d)
    return result


def get_perbandingan_meja(tahun: int) -> Dict[str, Any]:
    """Perbandingan Meja A vs Meja B untuk tahun tertentu."""
    result = {}
    for meja in ['Meja A', 'Meja B']:
        stats = get_dashboard_stats(tahun=tahun, meja=meja)
        result[meja] = stats
    return result


def get_recent_progress(limit: int = 10) -> List[Progress]:
    """Mengambil progress terbaru."""
    return get_progress(limit=limit, order_by='created_at DESC')


def get_distinct_pekerjaan() -> List[str]:
    """Mengambil daftar pekerjaan yang unik."""
    rows = execute_query(
        "SELECT DISTINCT pekerjaan FROM progress ORDER BY pekerjaan",
        fetch='all'
    )
    return [r['pekerjaan'] for r in rows] if rows else []


def get_distinct_tahun() -> List[int]:
    """Mengambil daftar tahun yang ada di database."""
    rows = execute_query(
        "SELECT DISTINCT strftime('%Y', tanggal) as tahun FROM progress ORDER BY tahun DESC",
        fetch='all'
    )
    return [int(r['tahun']) for r in rows] if rows else []


# ============================================================
# HELPERS
# ============================================================

def _validate_progress(p: Progress):
    """Validasi data progress sebelum disimpan."""
    if not p.tanggal:
        raise ValueError("Tanggal tidak boleh kosong.")
    if p.meja not in (MEJA_A, MEJA_B):
        raise ValueError("Meja kerja harus Meja A atau Meja B.")
    if not p.nama_pic:
        raise ValueError("Nama PIC tidak boleh kosong.")
    if not p.pekerjaan:
        raise ValueError("Nama pekerjaan tidak boleh kosong.")
    if p.target is not None and p.target < 0:
        raise ValueError("Target tidak boleh negatif.")
    if p.realisasi is not None and p.realisasi < 0:
        raise ValueError("Realisasi tidak boleh negatif.")
    # Validasi format tanggal
    try:
        datetime.strptime(p.tanggal, '%Y-%m-%d')
    except (TypeError, ValueError):
        raise ValueError(f"Format tanggal tidak valid: {p.tanggal}. Gunakan YYYY-MM-DD.")


def _row_to_progress(row) -> Progress:
    """Mengkonversi row database ke objek Progress."""
    return Progress(
        id=row['id'],
        tanggal=row['tanggal'],
        meja=row['meja'],
        nama_pic=row['nama_pic'],
        pekerjaan=row['pekerjaan'],
        rincian_pengerjaan=row['rincian_pengerjaan'] or '',
        target=row['target'],
        realisasi=row['realisasi'],
        keterangan=row['keterangan'] or '',
        imported_from=row['imported_from'] or '',
        created_at=row['created_at'] or '',
        updated_at=row['updated_at'] or '',
    )


def hitung_status(realisasi, target, threshold_pct: float) -> str:
    """Fungsi utilitas hitung status pencapaian."""
    if realisasi is None:
        return STATUS_BELUM_DIISI
    if target is None or target <= 0:
        return STATUS_DATA_TIDAK_LENGKAP
    pct = (realisasi / target) * 100
    return STATUS_TERCAPAI if pct >= threshold_pct else STATUS_TIDAK_TERCAPAI


def format_angka(nilai: float, desimal: int = 0) -> str:
    """Format angka dengan pemisah ribuan Indonesia."""
    if nilai is None:
        return '-'
    if desimal == 0:
        return f"{int(nilai):,}".replace(',', '.')
    return f"{nilai:,.{desimal}f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def format_persen(nilai: float) -> str:
    """Format persentase Indonesia."""
    if nilai is None:
        return '-'
    return f"{nilai:.2f}%".replace('.', ',')


def format_tanggal(tanggal: str) -> str:
    """Format tanggal ISO untuk tampilan pengguna tanpa mengubah nilai database."""
    try:
        return datetime.strptime(tanggal, '%Y-%m-%d').strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return tanggal or '-'
