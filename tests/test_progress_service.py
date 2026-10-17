import pytest
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
