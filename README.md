 # Progress PLSCS Meja A & B

Aplikasi desktop lokal berbasis Python + Flet untuk mengelola progress pekerjaan Meja A dan Meja B.

## Menjalankan

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Database disimpan di `%LOCALAPPDATA%\ProgressPLSCS\progress_plscs.db`. Workbook sumber berada di `data\PROGRESS PLSCS MEJA A & B FIXED (1).xlsx`.

Sheet transaksi yang dipetakan adalah `DAY (MEJA A)` dan `DAY (MEJA B)`; sheet statistik dan rekap tidak diimpor sebagai transaksi.
