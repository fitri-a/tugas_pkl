"""
Model data dan operasi CRUD dasar
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import date


@dataclass
class PIC:
    id: Optional[int] = None
    nama: str = ""
    aktif: bool = True
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Progress:
    id: Optional[int] = None
    tanggal: str = ""           # ISO: YYYY-MM-DD
    meja: str = ""              # 'Meja A' atau 'Meja B'
    nama_pic: str = ""
    pekerjaan: str = ""
    rincian_pengerjaan: str = ""
    target: Optional[float] = None
    realisasi: Optional[float] = None
    keterangan: str = ""
    imported_from: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def progress_pct(self) -> Optional[float]:
        """Menghitung persentase progress. None jika target 0 atau kosong."""
        if self.target and self.target > 0 and self.realisasi is not None:
            return (self.realisasi / self.target) * 100
        return None

    @property
    def status(self) -> str:
        """Mengembalikan status pencapaian."""
        from app.services.progress_service import get_threshold_pct
        threshold = get_threshold_pct()

        if not self.nama_pic or not self.pekerjaan or self.realisasi is None:
            return "TIDAK TERCAPAI"
        if self.target is None or self.target <= 0:
            return "TIDAK TERCAPAI"
        pct = self.progress_pct
        if pct is None:
            return "TIDAK TERCAPAI"
        if pct >= threshold:
            return "TERCAPAI"
        return "TIDAK TERCAPAI"

    def get_status_with_threshold(self, threshold_pct: float) -> str:
        """Status dengan threshold yang bisa dikustomisasi (dalam %)."""
        if not self.nama_pic or not self.pekerjaan or self.realisasi is None:
            return "TIDAK TERCAPAI"
        if self.target is None or self.target <= 0:
            return "TIDAK TERCAPAI"
        pct = self.progress_pct
        if pct is None:
            return "TIDAK TERCAPAI"
        if pct >= threshold_pct:
            return "TERCAPAI"
        return "TIDAK TERCAPAI"


@dataclass
class Settings:
    achievement_threshold: float = 0.70
    report_year: int = 2026
    backup_dir: str = ""
    theme: str = "light"
    rows_per_page: int = 25
    date_format: str = "DD/MM/YYYY"


@dataclass
class RekapHarian:
    tanggal: str
    meja: str
    nama_pic: str
    pekerjaan: str
    total_target: float
    total_realisasi: float
    jumlah_entri: int

    @property
    def persentase(self) -> Optional[float]:
        if self.total_target and self.total_target > 0:
            return (self.total_realisasi / self.total_target) * 100
        return None


@dataclass
class RekapMingguan:
    minggu_ke: int
    tanggal_mulai: str
    tanggal_selesai: str
    label_minggu: str
    meja: str
    nama_pic: str
    pekerjaan: str
    total_target: float
    total_realisasi: float
    jumlah_hari: int

    @property
    def persentase(self) -> Optional[float]:
        if self.total_target and self.total_target > 0:
            return (self.total_realisasi / self.total_target) * 100
        return None


@dataclass
class RekapBulanan:
    bulan: int
    tahun: int
    nama_bulan: str
    meja: str
    total_target: float
    total_realisasi: float
    jumlah_hari: int

    @property
    def persentase(self) -> Optional[float]:
        if self.total_target and self.total_target > 0:
            return (self.total_realisasi / self.total_target) * 100
        return None
