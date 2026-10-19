"""Shell desktop Flet dengan halaman operasional utama."""
from datetime import date, datetime, timedelta
import os
import flet as ft

from app.config import COLORS, MEJA_OPTIONS, PEKERJAAN_OPTIONS, DB_PATH, BACKUP_DIR
from app.database.models import Progress
from app.services import progress_service as service
from app.services.backup_service import backup_database, restore_database, validate_backup, get_backup_dir
from app.services.excel_service import export_to_excel, import_excel_data, preview_excel_import


class AppShell:
    def __init__(self, page: ft.Page):
        self.page = page
        self.editing_id = None
        self.detail_status = None
        self.detail_filters = {}
        self.body = ft.Container(expand=True)
        self.notice = ft.SnackBar(content=ft.Text(''))
        self.page.snack_bar = self.notice
        self.render('Dashboard')

    def build(self):
        return ft.Row([self.sidebar(), ft.Column([self.topbar(), self.body], expand=True)], expand=True, spacing=0)

    def sidebar(self):
        items = ['Dashboard', 'Input Progress', 'Data Progress', 'Laporan Harian', 'Laporan Mingguan', 'Laporan Bulanan', 'Manajemen PIC', 'Pengaturan']
        return ft.Container(width=238, bgcolor=COLORS['sidebar_bg'], padding=20, content=ft.Column([
            ft.Text('PLSCS', size=28, weight=ft.FontWeight.BOLD, color='white'),
            ft.Text('Progress Meja A & B', color='#B8CCE3'),
            ft.Divider(color='#42617F'),
            *[ft.TextButton(item, on_click=lambda e, name=item: self.render(name), style=ft.ButtonStyle(color={'': '#D8E8F7'})) for item in items],
            ft.Container(expand=True),
            ft.Text('Lokal • SQLite', color='#9CB4CB', size=12),
        ], spacing=6))

    def topbar(self):
        return ft.Container(height=72, padding=ft.padding.symmetric(horizontal=28), bgcolor='white', content=ft.Row([
            ft.Text('Progress PLSCS', size=19, weight=ft.FontWeight.BOLD, color=COLORS['text_primary']),
            ft.Container(expand=True), ft.Text(datetime.now().strftime('%d/%m/%Y'), color=COLORS['text_secondary'])
        ]))

    def render(self, name):
        pages = {
            'Dashboard': self.dashboard,
            'Input Progress': self.input_progress,
            'Data Progress': self.data_progress,
            'Laporan Harian': self.daily_report,
            'Laporan Mingguan': self.weekly_report,
            'Laporan Bulanan': self.monthly_report,
            'Manajemen PIC': self.pic_management,
            'Pengaturan': self.settings,
        }
        self.body.content = ft.Container(expand=True, padding=28, content=pages.get(name, self.dashboard)())
        self.page.update()

    def title(self, title, subtitle=''):
        return ft.Column([ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=COLORS['text_primary']), ft.Text(subtitle, color=COLORS['text_secondary'])], spacing=4)

    def dashboard(self):
        settings = service.get_settings()
        tahun = ft.Dropdown(label='Tahun', width=145, value='Semua', options=[ft.dropdown.Option('Semua'), *[ft.dropdown.Option(str(y)) for y in service.get_distinct_tahun()]])
        period = ft.Dropdown(label='Periode grafik', width=155, value='monthly', options=[ft.dropdown.Option('daily', 'Harian'), ft.dropdown.Option('weekly', 'Mingguan'), ft.dropdown.Option('monthly', 'Bulanan'), ft.dropdown.Option('yearly', 'Tahunan')])
        content = ft.Column(spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)

        def current_filters():
            return {'tahun': None if tahun.value == 'Semua' else int(tahun.value)}

        def load(_=None):
            filters = current_filters()
            self.detail_filters = dict(filters)
            stats = service.get_dashboard_stats(**filters)
            statuses = service.get_dashboard_status_counts(**filters)
            periods = service.get_dashboard_period_data(period.value, **filters)
            pics = service.get_dashboard_pic_data(**filters)
            latest = service.get_progress(tahun=filters['tahun'], limit=settings.rows_per_page)
            content.controls = self._dashboard_content(stats, statuses, periods, pics, latest, period.value, filters, load)
            self.page.update()

        def reset(_):
            tahun.value = 'Semua'; period.value = 'monthly'
            load()

        filter_panel = self._panel(ft.Column([
            ft.Row([ft.Icon(ft.icons.FILTER_ALT_OUTLINED, color=COLORS['primary_light']), ft.Text('Filter analisis', size=16, weight=ft.FontWeight.BOLD), ft.Container(expand=True), ft.TextButton('Reset filter', icon=ft.icons.REFRESH, on_click=reset)], alignment=ft.MainAxisAlignment.START),
            ft.Row([tahun, period, ft.ElevatedButton('Terapkan', icon=ft.icons.TUNE, on_click=load)], wrap=True, spacing=10),
        ]))
        load()
        return ft.Column([self.title('Dashboard', 'Analisis pencapaian Progress PLSCS Meja A & B'), filter_panel, content], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    def _dashboard_content(self, stats, statuses, periods, pics, latest, period, filters, reload):
        target = stats.get('total_target', 0) or 0
        realisasi = stats.get('total_realisasi', 0) or 0
        achievement = (realisasi / target * 100) if target else None
        cards = [
            ('Total pekerjaan', service.format_angka(stats.get('total_entri', 0)), 'Catatan pada filter aktif', COLORS['primary_light'], ft.icons.WORK_OUTLINE),
            ('Total target', service.format_angka(target), 'Akumulasi target valid', COLORS['info'], ft.icons.FLAG_OUTLINED),
            ('Total realisasi', service.format_angka(realisasi), 'Akumulasi realisasi valid', COLORS['success'], ft.icons.TRENDING_UP),
            ('Pencapaian', service.format_persen(achievement), 'Realisasi dibagi target', COLORS['warning'], ft.icons.SPEED),
            ('Selesai', str(statuses.get('selesai', 0)), 'Memenuhi batas pencapaian', COLORS['success'], ft.icons.CHECK_CIRCLE_OUTLINE),
            ('Tidak tercapai', str(statuses.get('proses', 0)), 'Di bawah batas pencapaian', COLORS['danger'], ft.icons.PENDING_ACTIONS),
        ]
        return [
            ft.Row([self._kpi_card(*item, on_click=(lambda _, s='TERCAPAI': self._open_status_detail(s)) if item[0] == 'Selesai' else (lambda _, s='TIDAK TERCAPAI': self._open_status_detail(s)) if item[0] == 'Tidak tercapai' else None) for item in cards], wrap=True, spacing=12, run_spacing=12),
            ft.Row([self._panel(ft.Column([ft.Text('Target vs realisasi', size=17, weight=ft.FontWeight.BOLD), ft.Text(self._period_label(period), size=12, color=COLORS['text_secondary']), self._bar_chart(periods)]), expand=2), self._panel(ft.Column([ft.Text('Status pekerjaan', size=17, weight=ft.FontWeight.BOLD), self._status_chart(statuses)]), expand=1)], spacing=14),
            ft.Row([self._panel(ft.Column([ft.Text('Tren pencapaian', size=17, weight=ft.FontWeight.BOLD), self._line_chart(periods)]), expand=2), self._panel(ft.Column([ft.Text('Distribusi PIC', size=17, weight=ft.FontWeight.BOLD), self._pic_chart(pics)]), expand=1)], spacing=14),
            self._panel(self._desk_comparison(filters)),
            self._panel(self._latest_table(latest, reload)),
            self._panel(self._insights(stats, statuses, pics, latest)),
        ]

    def _panel(self, content, expand=None):
        properties = {
            'bgcolor': 'white',
            'border_radius': 16,
            'padding': 18,
            'shadow': ft.BoxShadow(blur_radius=18, color='#140F2340', offset=ft.Offset(0, 5)),
            'content': content,
        }
        if expand is not None:
            properties['expand'] = expand
        return ft.Container(**properties)

    def _kpi_card(self, title, value, detail, color, icon, on_click=None):
        action = None
        if title in ('Selesai', 'Tidak tercapai'):
            action = ft.TextButton('Lihat semua data', icon=ft.icons.OPEN_IN_NEW, on_click=on_click,
                                   style=ft.ButtonStyle(color=COLORS['primary_light'], bgcolor='#EEF4FA',
                                                        shape=ft.RoundedRectangleBorder(radius=18),
                                                        padding=ft.padding.symmetric(horizontal=10, vertical=6)))
        controls = [
            ft.Row([ft.Container(width=34, height=34, border_radius=10, bgcolor=color, alignment=ft.alignment.center, content=ft.Icon(icon, color='white', size=18)), ft.Container(expand=True), ft.Icon(ft.icons.ARROW_OUTWARD, size=14, color=COLORS['text_light'])]),
            ft.Text(title, size=12, color=COLORS['text_secondary']),
            ft.Text(value, size=23, weight=ft.FontWeight.BOLD, color=COLORS['text_primary']),
            ft.Text(detail, size=11, color=COLORS['text_secondary']),
        ]
        if action is not None:
            controls.append(action)
        return ft.Container(width=190, padding=16, bgcolor='white', border_radius=16, on_click=on_click, animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT), shadow=ft.BoxShadow(blur_radius=16, color='#120F2340', offset=ft.Offset(0, 4)), content=ft.Column([
            *controls
        ], spacing=7))

    def _open_status_detail(self, status):
        self.detail_status = status
        self.render('Data Progress')

    def _bar_chart(self, rows):
        if not rows:
            return self._empty_chart('Belum ada data pada periode ini.')
        maximum = max(max(float(r['target'] or 0), float(r['realisasi'] or 0)) for r in rows) or 1
        groups = []
        for i, row in enumerate(rows[-8:]):
            groups.append(ft.BarChartGroup(x=i, bar_rods=[ft.BarChartRod(from_y=0, to_y=float(row['target'] or 0), width=9, color=COLORS['primary_light'], tooltip=f"Target {service.format_angka(row['target'])}"), ft.BarChartRod(from_y=0, to_y=float(row['realisasi'] or 0), width=9, color=COLORS['success'], tooltip=f"Realisasi {service.format_angka(row['realisasi'])}")]))
        return ft.BarChart(bar_groups=groups, max_y=maximum * 1.15, height=250, interactive=True, tooltip_bgcolor=COLORS['primary_dark'], bottom_axis=ft.ChartAxis(labels=[ft.ChartAxisLabel(value=i, label=ft.Text(str(r['periode'])[-7:], size=10)) for i, r in enumerate(rows[-8:])], labels_size=30), left_axis=ft.ChartAxis(labels_size=35), horizontal_grid_lines=ft.ChartGridLines(color=COLORS['border'], width=1))

    def _line_chart(self, rows):
        if not rows:
            return self._empty_chart('Belum ada data tren.')
        points = []
        for i, row in enumerate(rows[-12:]):
            target, realisasi = float(row['target'] or 0), float(row['realisasi'] or 0)
            points.append(ft.LineChartDataPoint(i, realisasi / target * 100 if target else 0))
        return ft.LineChart(data_series=[ft.LineChartData(data_points=points, stroke_width=3, color=COLORS['success'], curved=True, point=True)], min_y=0, max_y=max(100, max((p.y for p in points), default=100) * 1.1), height=250, interactive=True, tooltip_bgcolor=COLORS['primary_dark'], left_axis=ft.ChartAxis(labels_size=35), bottom_axis=ft.ChartAxis(labels=[ft.ChartAxisLabel(value=i, label=ft.Text(str(r['periode'])[-7:], size=10)) for i, r in enumerate(rows[-12:])], labels_size=30), horizontal_grid_lines=ft.ChartGridLines(color=COLORS['border'], width=1))

    def _status_chart(self, statuses):
        values = [('Selesai', statuses.get('selesai', 0), COLORS['success']), ('Tidak tercapai', statuses.get('proses', 0), COLORS['danger'])]
        total = sum(v for _, v, _ in values)
        if not total:
            return self._empty_chart('Belum ada status pekerjaan.')
        sections = [ft.PieChartSection(value=v, title=f'{v}\n{v / total * 100:.0f}%', color=c, radius=65, title_style=ft.TextStyle(size=11, color='white', weight=ft.FontWeight.BOLD)) for _, v, c in values if v]
        legend = ft.Column([ft.Row([ft.Container(width=10, height=10, bgcolor=c, border_radius=5), ft.Text(f'{name}: {value}', size=11)]) for name, value, c in values], spacing=4)
        return ft.Column([ft.PieChart(sections=sections, height=180, center_space_radius=35), legend], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _pic_chart(self, rows):
        if not rows:
            return self._empty_chart('Belum ada data PIC.')
        maximum = max(int(r['jumlah']) for r in rows) or 1
        return ft.Column([ft.Row([ft.Text(str(r['nama_pic']), width=110, size=11), ft.ProgressBar(value=int(r['jumlah']) / maximum, color=COLORS['primary_light'], bgcolor=COLORS['surface_dark'], expand=True), ft.Text(str(r['jumlah']), width=25, size=11, text_align=ft.TextAlign.RIGHT)]) for r in rows], spacing=13)

    def _desk_comparison(self, filters):
        rows = []
        for desk in MEJA_OPTIONS:
            desk_filters = dict(filters)
            desk_filters['meja'] = desk
            stats = service.get_dashboard_stats(**desk_filters)
            pct = stats.get('persentase_keseluruhan')
            rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(desk, weight=ft.FontWeight.BOLD)), ft.DataCell(ft.Text(str(stats.get('total_entri', 0)))), ft.DataCell(ft.Text(service.format_angka(stats.get('total_target', 0)))), ft.DataCell(ft.Text(service.format_angka(stats.get('total_realisasi', 0)))), ft.DataCell(ft.Text(service.format_persen(pct)))]))
        return ft.Column([ft.Text('Perbandingan Meja A dan Meja B', size=17, weight=ft.FontWeight.BOLD), ft.Text('Pencapaian dihitung dari total realisasi dibagi total target.', size=12, color=COLORS['text_secondary']), ft.DataTable(columns=[ft.DataColumn(ft.Text(x)) for x in ['Meja', 'Pekerjaan', 'Target', 'Realisasi', 'Pencapaian']], rows=rows)])

    def _empty_chart(self, message):
        return ft.Container(height=180, alignment=ft.alignment.center, content=ft.Column([ft.Icon(ft.icons.INSERT_CHART_OUTLINED, size=34, color=COLORS['text_light']), ft.Text(message, color=COLORS['text_secondary'])], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER))

    def _latest_table(self, rows, reload):
        header = ft.Row([ft.Text('Rincian pekerjaan terbaru', size=17, weight=ft.FontWeight.BOLD), ft.Container(expand=True), ft.TextButton('Lihat semua data', icon=ft.icons.OPEN_IN_NEW, on_click=lambda _: self.render('Data Progress'))])
        if not rows:
            return ft.Column([header, ft.Text('Belum ada data pekerjaan pada filter aktif.', color=COLORS['text_secondary'])])
        table_rows = []
        for index, row in enumerate(rows, 1):
            table_rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(str(index))), ft.DataCell(ft.Text(service.format_tanggal(row.tanggal))), ft.DataCell(ft.Text(row.meja)), ft.DataCell(ft.Text(row.nama_pic)), ft.DataCell(ft.Text(row.pekerjaan, max_lines=1)), ft.DataCell(ft.Text(service.format_angka(row.target))), ft.DataCell(ft.Text(service.format_angka(row.realisasi))), ft.DataCell(self._status_badge(row.status))], on_select_changed=lambda _, pid=row.id: self._show_progress_detail(pid)))
        return ft.Column([header, ft.Container(content=ft.DataTable(columns=[ft.DataColumn(ft.Text(x)) for x in ['No', 'Tanggal', 'Meja', 'PIC', 'Pekerjaan', 'Target', 'Realisasi', 'Status']], rows=table_rows), clip_behavior=ft.ClipBehavior.HARD_EDGE)], scroll=ft.ScrollMode.AUTO)

    def _status_badge(self, status):
        color = {'TERCAPAI': COLORS['success'], 'TIDAK TERCAPAI': COLORS['danger'], 'BELUM DIISI': COLORS['warning']}.get(status, COLORS['text_light'])
        return ft.Container(padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=12, bgcolor=color, content=ft.Text(status, size=10, color='white', weight=ft.FontWeight.BOLD))

    def _show_progress_detail(self, progress_id):
        row = service.get_progress_by_id(progress_id)
        if not row:
            return
        self.page.dialog = ft.AlertDialog(title=ft.Text('Detail pekerjaan'), content=ft.Column([ft.Text(f'{row.tanggal} | {row.meja} | {row.nama_pic}'), ft.Text(row.pekerjaan, weight=ft.FontWeight.BOLD), ft.Text(row.rincian_pengerjaan or 'Tidak ada rincian.'), ft.Text(f'Target: {service.format_angka(row.target)} | Realisasi: {service.format_angka(row.realisasi)} | Pencapaian: {service.format_persen(row.progress_pct)}'), self._status_badge(row.status)], tight=True), actions=[ft.TextButton('Tutup', on_click=lambda _: setattr(self.page.dialog, 'open', False))])
        self.page.dialog.open = True
        self.page.update()

    def _insights(self, stats, statuses, pics, latest):
        if not stats.get('total_entri'):
            return ft.Column([ft.Text('Insight pekerjaan', size=17, weight=ft.FontWeight.BOLD), ft.Text('Analisis belum dapat dibuat karena belum ada data pada filter aktif.', color=COLORS['text_secondary'])])
        highest_pic = pics[0]['nama_pic'] if pics else '-'
        return ft.Column([ft.Text('Insight pekerjaan', size=17, weight=ft.FontWeight.BOLD), ft.Text(f"• {stats['total_entri']} pekerjaan dianalisis pada periode/filter aktif."), ft.Text(f"• {statuses.get('selesai', 0)} pekerjaan memenuhi batas pencapaian; {statuses.get('proses', 0)} belum memenuhi batas (termasuk data tidak lengkap)."), ft.Text(f"• PIC dengan jumlah catatan terbanyak pada filter ini: {highest_pic}. Ini menunjukkan volume catatan, bukan penilaian kinerja.")])

    def _period_label(self, period):
        return {'daily': 'Harian', 'weekly': 'Mingguan', 'monthly': 'Bulanan', 'yearly': 'Tahunan'}.get(period, 'Bulanan')

    def card(self, label, value, color):
        return ft.Container(width=210, padding=18, bgcolor='white', border_radius=14, border=ft.border.only(left=ft.BorderSide(5, color)), content=ft.Column([ft.Text(label, color=COLORS['text_secondary']), ft.Text(value, size=25, weight=ft.FontWeight.BOLD)]))

    def date_picker(self, label, iso_value=None, width=180, default_today=True):
        """Membuat field tanggal read-only dan DatePicker Flet yang menyimpan ISO."""
        selected_date = None
        if iso_value:
            try:
                selected_date = datetime.strptime(iso_value, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                selected_date = None
        if selected_date is None and default_today:
            selected_date = date.today()
        field = ft.TextField(
            label=label,
            value=selected_date.strftime('%d/%m/%Y') if selected_date else '',
            read_only=True,
            width=width,
            suffix=ft.IconButton(ft.icons.CALENDAR_MONTH, tooltip='Pilih tanggal'),
        )
        picker = ft.DatePicker(
            value=selected_date,
            first_date=date(2000, 1, 1),
            last_date=date(2100, 12, 31),
            date_picker_entry_mode=ft.DatePickerEntryMode.CALENDAR_ONLY,
        )
        field.data = {'iso': selected_date.isoformat() if selected_date else None, 'picker': picker}
        field.suffix.on_click = lambda _: self.page.open(picker)

        def changed(e):
            if picker.value:
                field.data['iso'] = picker.value.date().isoformat()
                field.value = picker.value.strftime('%d/%m/%Y')
                self.page.update()

        picker.on_change = changed
        self.page.overlay.append(picker)
        return field

    def input_progress(self):
        existing = service.get_progress_by_id(self.editing_id) if self.editing_id else None
        tanggal = self.date_picker('Tanggal', existing.tanggal if existing else None)
        meja = ft.Dropdown(label='Meja kerja', width=150, options=[ft.dropdown.Option(x) for x in MEJA_OPTIONS], value=existing.meja if existing else MEJA_OPTIONS[0])
        pic_options = service.get_pic_names(aktif_only=True)
        if existing and existing.nama_pic and existing.nama_pic not in pic_options:
            pic_options.insert(0, existing.nama_pic)
        pic = ft.Dropdown(label='Nama PIC', value=existing.nama_pic if existing else None, width=230, options=[ft.dropdown.Option(value) for value in pic_options])
        pekerjaan_options = list(PEKERJAAN_OPTIONS)
        if existing and existing.pekerjaan and existing.pekerjaan not in pekerjaan_options:
            pekerjaan_options.insert(0, existing.pekerjaan)
        pekerjaan = ft.Dropdown(label='Pekerjaan', value=existing.pekerjaan if existing else None, expand=True, options=[ft.dropdown.Option(x) for x in pekerjaan_options])
        rincian = ft.TextField(label='Rincian pengerjaan', value=existing.rincian_pengerjaan if existing else '', multiline=True, min_lines=2)
        target = ft.TextField(label='Target', value=str(existing.target) if existing and existing.target is not None else '', width=150, keyboard_type=ft.KeyboardType.NUMBER)
        realisasi = ft.TextField(label='Realisasi', value=str(existing.realisasi) if existing and existing.realisasi is not None else '', width=150, keyboard_type=ft.KeyboardType.NUMBER)
        keterangan = ft.TextField(label='Keterangan', value=existing.keterangan if existing else '', multiline=True, min_lines=2)

        def parse_num(value):
            if not value.strip():
                return None
            return float(value.replace('.', '').replace(',', '.'))

        def save(e):
            try:
                p = Progress(tanggal=tanggal.data['iso'], meja=meja.value, nama_pic=(pic.value or '').strip(), pekerjaan=(pekerjaan.value or '').strip(), rincian_pengerjaan=rincian.value.strip(), target=parse_num(target.value), realisasi=parse_num(realisasi.value), keterangan=keterangan.value.strip())
                if service.check_duplicate(p.tanggal, p.meja, p.nama_pic, p.pekerjaan, exclude_id=self.editing_id):
                    self.toast('Peringatan: data dengan kombinasi yang sama sudah ada.')
                    return
                if self.editing_id:
                    p.id = self.editing_id
                    service.update_progress(p)
                else:
                    service.add_progress(p)
                service.ensure_pic_exists(p.nama_pic)
                was_edit = bool(p.id)
                self.editing_id = None
                self.toast('Data progress berhasil diperbarui.' if was_edit else 'Data progress berhasil disimpan.')
                self.render('Data Progress')
            except Exception as ex:
                self.toast(str(ex), error=True)

        def reset(e):
            for field in [rincian, target, realisasi, keterangan]: field.value = ''
            pic.value = None
            pekerjaan.value = None
            tanggal.data['iso'] = date.today().isoformat()
            tanggal.value = date.today().strftime('%d/%m/%Y')
            tanggal.data['picker'].value = date.today()
            self.page.update()

        return ft.Column([self.title('Edit Progress' if existing else 'Input Progress Harian', 'Catat pekerjaan dan hasil aktual ke database lokal'), ft.Row([tanggal, meja, pic]), ft.Row([pekerjaan]), rincian, ft.Row([target, realisasi]), keterangan, ft.Row([ft.ElevatedButton('Simpan', on_click=save), ft.OutlinedButton('Reset Form', on_click=reset), ft.TextButton('Batal', on_click=lambda _: (setattr(self, 'editing_id', None), self.render('Data Progress')))])], scroll=ft.ScrollMode.AUTO)

    def data_progress(self):
        tanggal_mulai = self.date_picker('Tanggal mulai', width=170, default_today=False)
        tanggal_selesai = self.date_picker('Tanggal selesai', width=170, default_today=False)
        initial_year = self.detail_filters.get('tahun')
        tahun = ft.Dropdown(label='Tahun', width=130, options=[ft.dropdown.Option('Semua'), *[ft.dropdown.Option(str(y)) for y in service.get_distinct_tahun()]], value=str(initial_year) if initial_year else 'Semua')
        meja = ft.Dropdown(label='Meja', width=150, options=[ft.dropdown.Option('Semua'), *[ft.dropdown.Option(x) for x in MEJA_OPTIONS]], value=self.detail_filters.get('meja') or 'Semua')
        if self.detail_filters.get('tanggal_mulai'):
            tanggal_mulai.data['iso'] = self.detail_filters['tanggal_mulai']
            tanggal_mulai.value = service.format_tanggal(self.detail_filters['tanggal_mulai'])
        if self.detail_filters.get('tanggal_selesai'):
            tanggal_selesai.data['iso'] = self.detail_filters['tanggal_selesai']
            tanggal_selesai.value = service.format_tanggal(self.detail_filters['tanggal_selesai'])
        table = ft.DataTable(columns=[ft.DataColumn(ft.Text(x)) for x in ['Tanggal', 'Meja', 'PIC', 'Pekerjaan', 'Target', 'Realisasi', 'Progress', 'Status', 'Aksi']], rows=[])
        count_label = ft.Text('', color=COLORS['text_secondary'])

        def load(e=None):
            data = service.get_progress(tahun=None if tahun.value == 'Semua' else int(tahun.value), status=self.detail_status, tanggal_mulai=tanggal_mulai.data['iso'], tanggal_selesai=tanggal_selesai.data['iso'], meja=None if meja.value == 'Semua' else meja.value)
            count_label.value = f'{len(data)} data ditemukan'
            table.rows = [ft.DataRow(cells=[ft.DataCell(ft.Text(service.format_tanggal(p.tanggal))), ft.DataCell(ft.Text(p.meja)), ft.DataCell(ft.Text(p.nama_pic)), ft.DataCell(ft.Text(p.pekerjaan, max_lines=2)), ft.DataCell(ft.Text(service.format_angka(p.target))), ft.DataCell(ft.Text(service.format_angka(p.realisasi))), ft.DataCell(ft.Text(service.format_persen(p.progress_pct))), ft.DataCell(ft.Text(p.status)), ft.DataCell(ft.Row([ft.IconButton(ft.icons.EDIT_OUTLINED, tooltip='Edit', on_click=lambda _, pid=p.id: edit(pid)), ft.IconButton(ft.icons.DELETE_OUTLINE, tooltip='Hapus', on_click=lambda _, pid=p.id: delete(pid))]))]) for p in data]
            self.page.update()

        def edit(progress_id):
            self.editing_id = progress_id
            self.render('Input Progress')

        def delete(progress_id):
            def confirm(_):
                service.delete_progress(progress_id)
                self.page.dialog.open = False
                load()
                self.toast('Data berhasil dihapus.')
            self.page.dialog = ft.AlertDialog(title=ft.Text('Hapus data?'), content=ft.Text('Data yang dihapus tidak dapat dipulihkan dari aplikasi.'), actions=[ft.TextButton('Batal', on_click=lambda _: setattr(self.page.dialog, 'open', False)), ft.ElevatedButton('Hapus', on_click=confirm)])
            self.page.dialog.open = True
            self.page.update()

        meja.on_change = load; tahun.on_change = load
        load()
        label = f"Data Progress{(' - ' + self.detail_status) if self.detail_status else ''}"
        return ft.Column([self.title(label, 'Pemantauan seluruh catatan'), ft.Row([tahun, tanggal_mulai, tanggal_selesai]), ft.Row([meja, ft.ElevatedButton('Cari', on_click=load), ft.OutlinedButton('Refresh', icon=ft.icons.REFRESH, on_click=load), ft.TextButton('Kembali Dashboard', on_click=lambda _: self.render('Dashboard'))]), count_label, ft.Container(content=table, bgcolor='white', padding=10)], scroll=ft.ScrollMode.AUTO, expand=True)

    def _report_meja_filter(self):
        meja = ft.Dropdown(label='Meja', width=145, value='Semua', options=[ft.dropdown.Option('Semua'), *[ft.dropdown.Option(x) for x in MEJA_OPTIONS]])
        return meja

    def _report_view(self, result, empty_text='Tidak ada data pekerjaan pada periode dan filter yang dipilih.'):
        summary = result['summary']
        cards = ft.Row([
            self.card('Jumlah pekerjaan', str(summary['jumlah']), COLORS['primary_light']),
            self.card('Total target', service.format_angka(summary['total_target']), COLORS['info']),
            self.card('Total realisasi', service.format_angka(summary['total_realisasi']), COLORS['success']),
            self.card('Pencapaian', service.format_persen(summary['persentase']), COLORS['warning']),
            self.card('Tercapai', str(summary['tercapai']), COLORS['success']),
            self.card('Tidak tercapai', str(summary['tidak_tercapai']), COLORS['danger']),
        ], wrap=True, spacing=10)
        columns = ['No.', 'Tanggal', 'Meja', 'Nama PIC', 'Pekerjaan', 'Rincian Pengerjaan', 'Target', 'Realisasi', 'Persentase Pencapaian', 'Status', 'Keterangan']
        table = ft.DataTable(columns=[ft.DataColumn(ft.Text(column)) for column in columns], rows=[])
        for row in result['rows']:
            values = [row['no'], service.format_tanggal(row['tanggal']), row['meja'], row['nama_pic'], row['pekerjaan'], row['rincian_pengerjaan'] or '-', service.format_angka(row['target']), service.format_angka(row['realisasi']), service.format_persen(row['persentase']), row['status'], row['keterangan'] or '-']
            table.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(str(value), selectable=True)) for value in values]))
        body = ft.Column([cards, ft.Text(f"{len(result['rows'])} data ditemukan"), ft.Container(content=table, bgcolor='white', padding=10, border_radius=8, clip_behavior=ft.ClipBehavior.HARD_EDGE)] if result['rows'] else [ft.Text(empty_text, color=COLORS['text_secondary'])], scroll=ft.ScrollMode.ALWAYS)
        return body

    def daily_report(self):
        tanggal = self.date_picker('Tanggal')
        meja = self._report_meja_filter()
        result = ft.Column()
        def load(e=None):
            data = service.get_report_detail(tanggal.data['iso'], tanggal.data['iso'], meja=None if meja.value == 'Semua' else meja.value)
            result.controls = [self._report_view(data)]
            self.page.update()
        def reset(e):
            tanggal.data['iso'] = date.today().isoformat(); tanggal.value = date.today().strftime('%d/%m/%Y'); meja.value = 'Semua'; load()
        return ft.Column([self.title('Laporan Harian', 'Seluruh rincian pekerjaan pada satu tanggal'), ft.Row([tanggal, meja, ft.ElevatedButton('Tampilkan', on_click=load), ft.OutlinedButton('Reset', on_click=reset)], wrap=True), result], scroll=ft.ScrollMode.AUTO, expand=True)

    def weekly_report(self):
        settings = service.get_settings()
        years = sorted(set(service.get_distinct_tahun() + [date.today().year, date.today().year + 1]), reverse=True)
        year = ft.Dropdown(label='Tahun', width=120, value=str(settings.report_year), options=[ft.dropdown.Option(str(value)) for value in years])
        week = ft.Dropdown(label='Minggu ISO', width=140, value=str(date.today().isocalendar().week), options=[ft.dropdown.Option(str(value)) for value in range(1, 54)])
        meja = self._report_meja_filter()
        result = ft.Column()
        def load(e=None):
            try:
                start = date.fromisocalendar(int(year.value), int(week.value), 1)
                end = start + timedelta(days=6)
                data = service.get_report_detail(start.isoformat(), end.isoformat(), meja=None if meja.value == 'Semua' else meja.value)
                result.controls = [ft.Text(f"Periode {service.format_tanggal(start.isoformat())} s.d. {service.format_tanggal(end.isoformat())}"), self._report_view(data)]
                self.page.update()
            except ValueError as ex: self.toast(f'Minggu tidak valid untuk tahun tersebut: {ex}', error=True)
        def reset(e):
            year.value = str(settings.report_year); week.value = '1'; meja.value = 'Semua'; load()
        return ft.Column([self.title('Laporan Mingguan', 'Seluruh rincian berdasarkan minggu ISO'), ft.Row([year, week, meja, ft.ElevatedButton('Tampilkan', on_click=load), ft.OutlinedButton('Reset', on_click=reset)], wrap=True), result], scroll=ft.ScrollMode.AUTO, expand=True)

    def monthly_report(self):
        settings = service.get_settings()
        years = sorted(set(service.get_distinct_tahun() + [date.today().year, date.today().year + 1]), reverse=True)
        year = ft.Dropdown(label='Tahun', width=120, value=str(settings.report_year), options=[ft.dropdown.Option(str(value)) for value in years])
        month = ft.Dropdown(label='Bulan', width=160, value=str(date.today().month), options=[ft.dropdown.Option(str(i), text=service.NAMA_BULAN[i]) for i in range(1, 13)])
        meja = self._report_meja_filter()
        result = ft.Column()
        def load(e=None):
            selected = int(month.value); start = date(int(year.value), selected, 1); end = date(int(year.value) + (selected == 12), selected % 12 + 1, 1) - timedelta(days=1)
            data = service.get_report_detail(start.isoformat(), end.isoformat(), meja=None if meja.value == 'Semua' else meja.value)
            result.controls = [self._report_view(data)]
            self.page.update()
        def reset(e):
            year.value = str(settings.report_year); month.value = '1'; meja.value = 'Semua'; load()
        return ft.Column([self.title('Laporan Bulanan', 'Seluruh rincian berdasarkan bulan dan tahun'), ft.Row([year, month, meja, ft.ElevatedButton('Tampilkan', on_click=load), ft.OutlinedButton('Reset', on_click=reset)], wrap=True), result], scroll=ft.ScrollMode.AUTO, expand=True)

    def pic_management(self):
        name = ft.TextField(label='Nama PIC', expand=True)
        listing = ft.Column()
        def load(e=None):
            listing.controls = [ft.Row([ft.Text(p.nama, expand=True), ft.Text('Aktif' if p.aktif else 'Nonaktif'), ft.TextButton('Aktifkan' if not p.aktif else 'Nonaktifkan', on_click=lambda _, p=p: (service.toggle_pic_aktif(p.id, not p.aktif), load()))]) for p in service.get_all_pic()]
            self.page.update()
        def add(e):
            try: service.add_pic(name.value); name.value = ''; load()
            except Exception as ex: self.toast(str(ex), error=True)
        load()
        return ft.Column([self.title('Manajemen PIC'), ft.Row([name, ft.ElevatedButton('Tambah PIC', on_click=add)]), listing], scroll=ft.ScrollMode.AUTO)

    def settings(self):
        current = service.get_settings()
        threshold = ft.TextField(label='Batas tercapai (0-1)', value=str(current.achievement_threshold), width=200)
        year = ft.TextField(label='Tahun laporan', value=str(current.report_year), width=180)
        def save(e):
            try:
                value = float(threshold.value)
                if not 0 <= value <= 1: raise ValueError('Batas harus antara 0 dan 1.')
                service.save_setting('achievement_threshold', str(value)); service.save_setting('report_year', str(int(year.value))); self.toast('Pengaturan tersimpan.'); self.render('Dashboard')
            except Exception as ex: self.toast(str(ex), error=True)
        def backup(e):
            try:
                actual = backup_database()
                self.toast(f'Backup tervalidasi dan tersimpan di: {actual}')
            except Exception as ex: self.toast(str(ex), error=True)

        def open_backup_folder(_):
            try:
                folder = get_backup_dir()
                os.startfile(str(folder))
            except Exception as ex:
                self.toast(f'Folder backup tidak dapat dibuka: {ex}', error=True)

        def import_result(e):
            if not e.files:
                return
            filepath = e.files[0].path
            preview = preview_excel_import(filepath)
            summary = f"Preview {preview['rows_valid']} valid, {preview['rows_invalid']} tidak valid, {preview['duplicate_count']} duplikat."
            def confirm(_):
                result = import_excel_data(filepath)
                self.toast(f"Impor selesai: {result['rows_imported']} baris masuk, {result['rows_skipped']} duplikat dilewati.", error=not result['success'])
            self.page.dialog = ft.AlertDialog(title=ft.Text('Konfirmasi impor Excel'), content=ft.Text(summary + '\nSheet transaksi: DAY (MEJA A) dan DAY (MEJA B).'), actions=[ft.TextButton('Batal', on_click=lambda _: setattr(self.page.dialog, 'open', False)), ft.ElevatedButton('Lanjutkan', on_click=confirm)])
            self.page.dialog.open = True
            self.page.update()

        def export_result(e):
            if not e.path:
                return
            try:
                export_to_excel(e.path)
                self.toast(f'Ekspor berhasil: {e.path}')
            except Exception as ex:
                self.toast(str(ex), error=True)

        importer = ft.FilePicker(on_result=import_result)
        exporter = ft.FilePicker(on_result=export_result)
        self.page.overlay.extend([importer, exporter])

        def choose_import(_): importer.pick_files(allow_multiple=False, allowed_extensions=['xlsx'])
        def choose_export(_): exporter.save_file(file_name=f"progress_plscs_{date.today().isoformat()}.xlsx", allowed_extensions=['xlsx'])

        def restore_result(e):
            if not e.files:
                return
            filepath = e.files[0].path
            if not validate_backup(filepath):
                self.toast('File backup tidak valid.', error=True)
                return
            def confirm(_):
                try:
                    restore_database(filepath)
                    self.page.dialog.open = False
                    self.toast('Restore berhasil. Buka ulang aplikasi untuk memuat seluruh data.')
                except Exception as ex:
                    self.toast(str(ex), error=True)
            self.page.dialog = ft.AlertDialog(title=ft.Text('Konfirmasi restore'), content=ft.Text('Restore akan mengganti database aktif. Pastikan backup terbaru sudah tersedia.'), actions=[ft.TextButton('Batal', on_click=lambda _: setattr(self.page.dialog, 'open', False)), ft.ElevatedButton('Restore', on_click=confirm)])
            self.page.dialog.open = True
            self.page.update()

        restorer = ft.FilePicker(on_result=restore_result)
        self.page.overlay.append(restorer)
        def choose_restore(_): restorer.pick_files(allow_multiple=False, allowed_extensions=['db'])

        return ft.Column([self.title('Pengaturan', 'Konfigurasi aplikasi dan data'), ft.Text(f'Database aktif: {DB_PATH}', selectable=True, size=12), ft.Text(f'Folder backup aktif: {get_backup_dir()}', selectable=True, size=12), ft.Row([threshold, year]), ft.Row([ft.ElevatedButton('Simpan Pengaturan', on_click=save), ft.OutlinedButton('Backup Database', on_click=backup), ft.OutlinedButton('Buka Folder Backup', icon=ft.icons.FOLDER_OPEN, on_click=open_backup_folder), ft.OutlinedButton('Restore Database', on_click=choose_restore), ft.OutlinedButton('Impor Excel', on_click=choose_import), ft.OutlinedButton('Ekspor Excel', on_click=choose_export)])])

    def toast(self, message, error=False):
        self.notice.content = ft.Text(message)
        self.notice.bgcolor = COLORS['danger'] if error else COLORS['success']
        self.notice.open = True
        self.page.update()
