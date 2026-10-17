import flet as ft
from app.config import COLORS
from app.services.progress_service import get_dashboard_stats, get_settings, format_angka, format_persen


class DashboardView:
    def __init__(self, page):
        self.page = page

    def build(self):
        settings = get_settings()
        stats = get_dashboard_stats(settings.report_year)
        cards = [
            ('Total Target', format_angka(stats.get('total_target', 0)), COLORS['primary_light']),
            ('Total Realisasi', format_angka(stats.get('total_realisasi', 0)), COLORS['success']),
            ('Pencapaian', format_persen(stats.get('persentase_keseluruhan', 0)), COLORS['info']),
            ('Entri Tercapai', str(stats.get('jumlah_tercapai', 0)), COLORS['warning']),
        ]
        return ft.Row([
            self._sidebar(),
            ft.Container(expand=True, padding=32, content=ft.Column([
                ft.Text('Dashboard Progress', size=30, weight=ft.FontWeight.BOLD, color=COLORS['text_primary']),
                ft.Text(f"Ringkasan aktual tahun {settings.report_year}", color=COLORS['text_secondary']),
                ft.Row([self._card(*card) for card in cards], spacing=16, wrap=True),
                ft.Container(margin=ft.margin.only(top=24), padding=24, bgcolor='white', border_radius=16,
                    content=ft.Column([
                        ft.Text('Status pekerjaan', size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{stats.get('jumlah_tercapai', 0)} tercapai | {stats.get('jumlah_tidak_tercapai', 0)} belum mencapai batas (termasuk data tidak lengkap)", color=COLORS['text_secondary']),
                        ft.ProgressBar(value=min(stats.get('persentase_keseluruhan', 0) / 100, 1), color=COLORS['success'], bgcolor=COLORS['surface_dark']),
                    ])),
            ]))
        ], expand=True, spacing=0)

    def _sidebar(self):
        return ft.Container(width=240, bgcolor=COLORS['sidebar_bg'], padding=20, content=ft.Column([
            ft.Text('PLSCS', size=28, weight=ft.FontWeight.BOLD, color='white'),
            ft.Text('Meja A & B', color='#B8CCE3'),
            ft.Divider(color='#42617F'),
            ft.Text('DASHBOARD', color='white', weight=ft.FontWeight.BOLD),
            ft.Text('Input Progress', color='#B8CCE3'),
            ft.Text('Data Progress', color='#B8CCE3'),
            ft.Text('Laporan', color='#B8CCE3'),
            ft.Text('Manajemen PIC', color='#B8CCE3'),
            ft.Text('Pengaturan', color='#B8CCE3'),
        ], spacing=18))

    def _card(self, title, value, color):
        return ft.Container(width=205, padding=20, bgcolor='white', border_radius=16,
            border=ft.border.only(left=ft.BorderSide(5, color)), content=ft.Column([
                ft.Text(title, color=COLORS['text_secondary']),
                ft.Text(value, size=25, weight=ft.FontWeight.BOLD, color=COLORS['text_primary']),
            ], spacing=8))
