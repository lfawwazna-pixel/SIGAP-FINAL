# SIGAP

**Sistem Pengaturan Fase Lampu Adaptif Berbasis CCTV dan Deteksi Kendaraan YOLO.**

Implementasi lokal mencakup **Tahap 5** serta **deteksi dan tracking video Tahap 6**. React/TypeScript menampilkan login, monitor, kendali dan ruang simulasi; FastAPI menyediakan autentikasi, pengirim keputusan adaptif, decoder video bersama serta eksperimen per akun; PostgreSQL menyimpan akun/sesi; ATCS beserta kendaraan sintetisnya berjalan sebagai proses mandiri. Sistem ini belum terhubung ke perangkat ATCS lapangan.

Yang tersedia: login/logout, peta tiga lajur dan ruas pintas kiri, kendaraan/antrean, ATCS fixed-time, eksperimen terpisah dengan EVP, keputusan adaptif antrean/tunggu/pemerataan, serta fallback. Video MP4 atau stream kamera terkonfigurasi menggunakan satu sesi per pendekat di tampilan ATCS dan SIGAP, dengan penandaan lajur/garis henti. **YOLO26s + ByteTrack dapat diaktifkan di SIGAP**; ATCS menampilkan video asli dari sesi yang sama. Inferensi memakai proses Python terpisah. Kendali Tahap 5 masih memakai data buatan; pengukuran antrean/tunggu dari video dan kendali berbasis AI belum terhubung. [Pemasangan dan hasil tracking Tahap 6](docs/stage6-tracking.md). Riwayat: [Tahap 5](docs/stage5-adaptive-video.md), [2E/2F](docs/traffic-simulation.md), [integrasi 3/4](docs/control-integration.md).

Baseline ATCS memakai U → T → S → B, hijau 85/150/95/100 detik, kuning 3 detik, semua merah minimum 2 detik, siklus nominal 450 detik. Saat SIGAP mengambil alih, ATCS menerapkan fase adaptif; gangguan memicu transisi kembali ke baseline. Area konflik dibaca dari kendaraan sintetis dan dapat memperpanjang semua merah. Login, logout, pergantian tampilan, reset eksperimen, atau backend berhenti tidak menghentikan proses ATCS. [Rincian ATCS](docs/atcs-fixed-time.md).

Revisi sebelum Tahap 5: tiga lajur per pendekat, tujuan dan lajur awal mobil sintetis dipilih terpisah, perpindahan satu/dua lajur bertahap di hulu, lajur kiri khusus ruas pintas dekat simpang, serta EVP masuk dari ujung belakang jalan. [Aturan dan verifikasi redesain](docs/three-lane-redesign.md).

## Konfigurasi lokal

Kebutuhan: Python 3.14, Node.js 24 LTS (atau 22.12+), npm, uv 0.11.15, dan PostgreSQL 17. Database dapat dijalankan melalui Docker Desktop. Dependency dikunci dalam `uv.lock` dan `frontend/package-lock.json`.

Semua perintah berikut dijalankan dari folder `PROJECT-SIGAP-ASTRA`.

Jika `.env` belum ada, salin `.env.example` dan isi `POSTGRES_PASSWORD`. Jangan menimpa konfigurasi yang sudah ada. Pada pengerjaan 2D, `.env` lokal sudah dibuat dengan password database acak; nilai tersebut tidak ditampilkan atau dimasukkan ke source code. Password database berbeda dari password operator.

```powershell
uv sync --locked --python 3.14
npm ci --prefix frontend
docker compose up -d --wait db
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

Konfigurasi utama:

| Variabel | Fungsi |
|---|---|
| POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD | Koneksi PostgreSQL lokal |
| SIGAP_DB_HOST / SIGAP_DB_PORT | Host/port yang dipakai proses Python lokal |
| POSTGRES_PORT | Port PostgreSQL pada host Docker |
| SIGAP_ATCS_BASE_URL | Alamat ATCS dari backend |
| SIGAP_CONTROL_API_KEY | Rahasia acak antarlayanan minimal 32 karakter; kosong menonaktifkan perintah kendali |
| ATCS_ENABLE_TEST_SOURCE / SIGAP_ADAPTIVE_SYNTHETIC | Keduanya true hanya untuk prototipe data buatan Tahap 5; default false |
| SIGAP_CAMERA_URLS | Pemetaan JSON U/T/S/B ke URL RTSP atau HTTP(S); hanya server |
| SIGAP_MEDIA_DIR | Direktori unggahan/kalibrasi; default work/media |
| BACKEND_PROXY_TARGET | Alamat backend dari Vite |
| VITE_API_BASE_URL | Prefix API publik; default /api; jangan isi rahasia |
| SIGAP_SESSION_SECONDS | Batas sesi absolut; default 28.800 detik / 8 jam |
| SIGAP_COOKIE_SECURE | false untuk HTTP localhost; true untuk HTTPS |
| SIGAP_ALLOWED_ORIGINS | Array JSON origin browser yang boleh login/logout |

Default port: frontend 5173, backend 8000, ATCS 8001, PostgreSQL 5432. Jika port frontend berubah, ubah origin yang diizinkan juga. `FRONTEND_PORT`, `BACKEND_PORT`, dan `ATCS_PORT` mengatur port host Compose; untuk proses lokal ubah argumen `--port` dan URL antar layanan.

Aturan simpang/waktu di `configs/intersection.json`, geometri peta di `configs/map-geometry.json`, parameter adaptif di `configs/adaptive-policy.json`. Path relatif `SIGAP_CONFIG_PATH` dihitung dari root proyek. Perubahan file konfigurasi memerlukan restart backend/ATCS. Simulasi tidak menyamakan skema simetris ini dengan ukuran/rambu lapangan.

## Menyiapkan akun operator

Akun tidak dibuat oleh migrasi, seed, atau startup. Buat secara eksplisit:

```powershell
.\.venv\Scripts\python.exe -m backend.app.accounts create --username operator.nama --display-name "Nama Operator"
```

Terminal meminta kata sandi dua kali tanpa menampilkannya. Default CLI menerima frasa sandi 15–128 karakter. Untuk pilihan eksplisit prototipe lokal tersedia `--allow-short-password`; tidak mengubah hashing atau pemeriksaan sesi. Tidak ada password pada argumen CLI, file konfigurasi, atau bundle frontend.

Semua akun tahap ini berperan **operator** dengan izin `monitor:read` dan `control:operate`. Nama pengguna tidak menentukan hak akses. Pembuatan akun dengan nama yang sudah dipakai ditolak. Kendali tetap memerlukan kesiapan sumber dan pemeriksaan server.

Pengelolaan dari terminal lokal:

```powershell
.\.venv\Scripts\python.exe -m backend.app.accounts reset-password --username operator.nama
.\.venv\Scripts\python.exe -m backend.app.accounts disable --username operator.nama
.\.venv\Scripts\python.exe -m backend.app.accounts enable --username operator.nama
```

Reset password, disable, dan enable mencabut sesi lama akun tersebut. Akun yang dibuat pada mesin ini adalah data lokal pengguna, bukan akun bawaan yang dibagikan bersama proyek.

## Menjalankan aplikasi

Buka tiga terminal dari root proyek:

**ATCS:**

```powershell
.\.venv\Scripts\python.exe -m uvicorn atcs_simulator.app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

**Backend:**

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
```

**Frontend:**

```powershell
npm run dev --prefix frontend
```

Buka [login lokal](http://127.0.0.1:5173/login). Setelah sesi terverifikasi, aplikasi berpindah ke `/monitor`. Akses langsung ke `/monitor` tanpa sesi kembali ke login. Nama operator/menu keluar ada di kanan atas. Pilih **Simulasi** untuk percobaan; siapkan ambulans/pemadam saat jeda, lalu tekan Mulai. ATCS utama tetap berjalan. Pilihan **SIGAP** menampilkan pengaturan kendali dan kesiapan integrasi. Berpindah tab tidak meminta override atau memulai ulang ATCS.

Hentikan terminal dengan Ctrl+C. ATCS tidak bergantung pada browser/backend/database untuk menjalankan timer. Gunakan satu instance/worker ATCS dan satu worker backend; state kendaraan serta eksperimen belum dibagikan lintas worker. Restart ATCS membuat sesi baru dan clearance awal. Restart backend menghapus eksperimen dalam memori, tetapi tidak menghapus sesi login PostgreSQL.

Untuk seluruh stack via Compose:

```powershell
docker compose config --quiet
docker compose up -d --wait db
docker compose build
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m backend.app.accounts create --username operator.nama --display-name "Nama Operator"
docker compose up -d atcs backend frontend
```

Jangan menjalankan Compose lengkap dan proses lokal pada port yang sama. `docker compose stop` menghentikan layanan tanpa menghapus volume. Container frontend masih Vite untuk pengembangan, bukan konfigurasi deployment. Build image aplikasi belum menjadi hasil verifikasi 2D; PostgreSQL Compose sudah dijalankan dan diuji.

## Endpoint dan diagnosis

| Alamat | Akses / fungsi |
|---|---|
| /api/health/live | Publik; proses backend hidup |
| /api/auth/login | POST JSON nama pengguna/password; origin + header aplikasi wajib |
| /api/auth/session | GET sesi terverifikasi dan identitas operator |
| /api/auth/logout | POST; sesi, origin, header aplikasi, dan token CSRF wajib |
| /api/health | Operator; kesehatan database/skema dan kapabilitas |
| /api/configuration | Operator; geometri dan baseline |
| /api/atcs/health | Operator; kesehatan ATCS |
| /api/atcs/status | Operator; fase, lampu, countdown dan sesi simulasi |
| /api/atcs/events | Operator; riwayat ATCS |
| /api/atcs/traffic | Operator; kendaraan sintetis dan sinyal ATCS pada satu snapshot |
| /api/simulation | Operator; GET ruang percobaan milik akun |
| /api/simulation/commands | POST; sesi/origin/CSRF; perintah hanya untuk eksperimen |
| :8000/docs | Dokumentasi endpoint backend |
| :8001/status, :8001/health | Diagnostik internal ATCS localhost; bukan jalur browser SIGAP |

`401` pada endpoint terlindungi berarti sesi tidak ada/tidak valid/kedaluwarsa atau akun tidak aktif. `403` berarti origin/header/CSRF tidak cocok. `429` membatasi percobaan masuk. `503 AUTH_UNAVAILABLE` berarti database atau skema akun belum dapat dipakai; periksa PostgreSQL dan migrasi. Tidak ada fallback autentikasi palsu jika database mati.

Lampu abu-abu/countdown — berarti status pengendali belum terverifikasi atau tidak mutakhir, bukan perintah semua merah. Semua merah dengan penahanan konflik memiliki alasan khusus. Riwayat memakai ID sesi ATCS, terpisah dari sesi login operator.

## Verifikasi

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m contracts.export_schemas --check
npm run contracts:check --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

Tes PostgreSQL nyata memerlukan database khusus berakhiran `_test`. Database `sigap_test` sudah dibuat terpisah saat pengerjaan 2D. Konfigurasikan `SIGAP_TEST_POSTGRES_DB`, `SIGAP_TEST_POSTGRES_USER`, `SIGAP_TEST_POSTGRES_HOST`, `SIGAP_TEST_POSTGRES_PORT`, dan `SIGAP_TEST_POSTGRES_PASSWORD` pada terminal pengujian. Ambil password melalui input tersembunyi, bukan menuliskannya di perintah:

```powershell
$env:SIGAP_TEST_POSTGRES_DB = 'sigap_test'
$env:SIGAP_TEST_POSTGRES_USER = 'sigap'
$env:SIGAP_TEST_POSTGRES_HOST = '127.0.0.1'
$env:SIGAP_TEST_POSTGRES_PORT = '5432'
$sigapTestSecret = Read-Host 'Password database pengujian' -AsSecureString
$env:SIGAP_TEST_POSTGRES_PASSWORD = [System.Net.NetworkCredential]::new('', $sigapTestSecret).Password
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:SIGAP_TEST_POSTGRES_PASSWORD
```

Tes menerapkan migrasi, membandingkan ORM, membuat akun pengujian unik, menguji login/restart/logout/pencabutan, lalu menghapus hanya akun pengujian yang dibuatnya. Tidak menghapus database atau akun operator lain. Tanpa konfigurasi uji, tes PostgreSQL dilewati secara eksplisit.

## Dokumen

- [Autentikasi operator 2D](docs/operator-auth.md)
- [Kendaraan dan percobaan 2E/2F](docs/traffic-simulation.md)
- [Monitor simpang 2C](docs/intersection-monitor.md)
- [Spesifikasi](docs/specification.md)
- [Arsitektur](docs/architecture.md)
- [Kontrak](docs/contracts.md)
- [ATCS fixed-time](docs/atcs-fixed-time.md)
- [Tahapan](docs/development-stages.md)
- [UI/UX](docs/ui-direction.md)
- [Dependency](docs/dependencies.md)
- [Verifikasi 2E/2F](docs/verification-2ef.md)
- [Integrasi dan fallback 3/4](docs/control-integration.md)
- [Verifikasi 3/4](docs/verification-34.md)

Implementasi berhenti di **Tahap 3/4**. Berikutnya **5 — Adaptif dengan data buatan** melalui protokol yang sudah tersedia. Pengirim lab 3/4 bersifat terprogram untuk menguji integrasi; heuristik adaptif/EVP sekarang masih berada di eksperimen 2F. CCTV/YOLO, keputusan operasional dari video dan deployment belum dibuat. Pemeriksaan visual browser masih tertunda karena pengaturan izin Browser Use tersimpan.
