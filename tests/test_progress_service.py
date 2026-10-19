import pytest
from app.services import progress_service
from app.services.progress_service import hitung_status, format_angka, format_persen, format_tanggal
from app.config import STATUS_TERCAPAI, STATUS_TIDAK_TERCAPAI, STATUS_BELUM_DIISI, STATUS_DATA_TIDAK_LENGKAP


def test_hitung_status_tercapai_dan_belum_tercapai():
    assert hitung_status(70, 100, 70) == STATUS_TERCAPAI
    assert hitung_status(69, 100, 70) == STATUS_TIDAK_TERCAPAI


def test_hitung_status_data_kosong():
    assert hitung_status(None, 100, 70) == STATUS_BELUM_DIISI
    assert hitung_status(10, 0, 70) == STATUS_DATA_TIDAK_LENGKAP


def test_format_indonesia():
    assert format_angka(1250) == '1.250'
    assert format_persen(85.5) == '85,50%'


def test_format_tanggal_tampilan():
    assert format_tanggal('2026-10-14') == '14/10/2026'
    assert format_tanggal('tanggal-lama') == 'tanggal-lama'


def test_pic_nonaktif_ditolak_untuk_progress_baru(monkeypatch):
    monkeypatch.setattr(progress_service, 'execute_query', lambda *args, **kwargs: {'aktif': 0})
    with pytest.raises(ValueError, match='Nonaktif'):
        progress_service._validate_new_progress_pic('PIC Lama')


def test_pic_aktif_diizinkan_untuk_progress_baru(monkeypatch):
    monkeypatch.setattr(progress_service, 'execute_query', lambda *args, **kwargs: {'aktif': 1})
    progress_service._validate_new_progress_pic('PIC Aktif')


def test_pic_belum_terdaftar_ditolak_untuk_progress_baru(monkeypatch):
    monkeypatch.setattr(progress_service, 'execute_query', lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match='belum terdaftar'):
        progress_service._validate_new_progress_pic('PIC Baru')

def test_dashboard_period_data_mencakup_seluruh_tahun_dan_mengabaikan_tanggal_invalid(monkeypatch):
    import sqlite3

    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE progress (tanggal TEXT, meja TEXT, target REAL, realisasi REAL)')
    conn.executemany(
        'INSERT INTO progress (tanggal, meja, target, realisasi) VALUES (?, ?, ?, ?)',
        [
            ('2025-12-20', 'Meja A', 100, 80),
            ('2026-01-05', 'Meja B', 200, 150),
            ('2026-03-10', 'Meja A', 300, 250),
            ('2026-10-01', 'Meja B', 400, 350),
            ('2027-02-01', 'Meja A', 500, 450),
            ('tanggal-tidak-valid', 'Meja A', 999, 999),
            (None, 'Meja B', 999, 999),
        ],
    )
    conn.commit()

    def execute_query(query, params=(), fetch=None):
        cursor = conn.execute(query, params)
        return cursor.fetchall() if fetch == 'all' else cursor.fetchone()

    monkeypatch.setattr(progress_service, 'execute_query', execute_query)

    rows = progress_service.get_dashboard_period_data('monthly')
    assert [row['periode'] for row in rows] == ['2025-12', '2026-01', '2026-03', '2026-10', '2027-02']
    assert [row['target'] for row in rows] == [100, 200, 300, 400, 500]
    assert [row['realisasi'] for row in rows] == [80, 150, 250, 350, 450]

    rows_2026 = progress_service.get_dashboard_period_data('monthly', tahun=2026)
    assert [row['periode'] for row in rows_2026] == ['2026-01', '2026-03', '2026-10']
    assert sum(row['target'] for row in rows_2026) == 900
    assert sum(row['realisasi'] for row in rows_2026) == 750

    daily = progress_service.get_dashboard_period_data('daily', meja='Meja A')
    assert [row['periode'] for row in daily] == ['2025-12-20', '2026-03-10', '2027-02-01']

    weekly = progress_service.get_dashboard_period_data('weekly')
    assert [row['periode'] for row in weekly] == ['2025-W50', '2026-W01', '2026-W10', '2026-W39', '2027-W05']

    yearly = progress_service.get_dashboard_period_data('yearly')
    assert [row['periode'] for row in yearly] == ['2025', '2026', '2027']
