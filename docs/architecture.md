# Arsitektur SIGAP sampai Tahap 4

```text
Browser React/TypeScript — login, ATCS / SIGAP / Simulasi, kendaraan, riwayat
    │ HTTP /api, melalui proxy Vite lokal
    ▼
Backend FastAPI ──────────► PostgreSQL (akun, hash sesi, migrasi)
    ├── autentikasi dan izin operator pada endpoint monitor
    ├── eksperimen per akun: jam, kendaraan, adaptif sintetis dan EVP terpisah
    │ HTTP baca + perintah operator; tidak memiliki timer ATCS
    ▼
ATCS FastAPI, satu worker
    ├── task runtime mandiri, jam monotonic
    ├── ManagedEngine → fixed-time, usulan SIGAP, transisi aman dan fallback
    ├── ControlSupervisor → sesi, heartbeat, umur data, tanda terima, jurnal
    ├── TrafficWorld → ConflictProvider lokal (kendaraan sintetis)
    └── buffer kejadian per sesi, tanpa database

configs/intersection.json → validasi backend dan ATCS saat startup
contracts/models.py + traffic.py + control.py → JSON Schema → tipe TS + validasi browser
```

| Komponen | Tanggung jawab yang tersedia | Belum tersedia |
|---|---|---|
| Frontend | Login, mode tampilan, peta/kendaraan, status, riwayat, kontrol eksperimen, panel kendali SIGAP | Video dan kendaraan dari CCTV |
| Backend | Autentikasi, proxy ATCS, adapter perintah operator, eksperimen terpisah per akun | Pengambilan keputusan dari CCTV |
| ATCS runtime | Memulai/menghentikan task, mengambil observasi konflik, memeriksa umur snapshot | Integrasi perangkat ATCS lapangan |
| ManagedEngine / ControlSupervisor | Baseline FixedTimeEngine, transisi aman, sesi SIGAP, watchdog heartbeat/data/rencana dan fallback | Pengaturan lampu fisik dan redundansi perangkat |
| Contracts/configs | Kontrak baca/perintah/tanda terima dan satu sumber waktu/geometri | Kalibrasi lapangan terverifikasi |
| Database | Akun operator dengan hash Argon2id, hash sesi dan kedaluwarsa, migrasi | Penyimpanan riwayat ATCS |

## Kepemilikan waktu dan status

Runtime dimulai sekali pada lifespan aplikasi ATCS, bukan saat request datang. Task berjalan pada proses ATCS dengan target pembaruan 100 ms dan menunggu deadline fase lebih dekat bila perlu. Pembacaan status/kejadian pada ATCS berjalan di event loop yang sama; pembacaan tidak mengubah state.

Mesin murni menerima jam dan observasi eksplisit sehingga batas waktu dapat diuji tanpa menunggu 450 detik. Simulasi lokal memakai jam monotonic dengan laju 1:1; tidak ada endpoint untuk mempercepat atau melompati fase.

Backend, browser, dan PostgreSQL boleh berhenti tanpa menghentikan ATCS. Kemandirian ini dibuktikan dengan tes proses nyata. Kemandirian proses tidak berarti kebal terhadap kegagalan host atau proses ATCS sendiri. Task yang gagal membuat status unavailable; restart memulai sesi baru.

Jalankan satu worker dan satu instance ATCS per simpang. State dan buffer saat ini lokal pada proses, bukan dibagikan antarreplika. Workers 1 dicantumkan pada Compose dan panduan lokal; multiworker/multireplika belum didukung.

## Kegagalan dan observasi

- Liveness menunjukkan proses API menjawab. Kesiapan mesin, database dan fitur lain diperiksa terpisah.
- Endpoint operator memerlukan sesi database pada setiap permintaan. Jika database tidak tersedia, autentikasi mengembalikan 503 dan data monitor tidak dibuka. Liveness backend tetap publik; proses ATCS tetap bekerja secara mandiri.
- ATCS 503 dengan laporan valid dapat berarti mesin faulted/stopped/stalled, sementara API masih hidup.
- Selama area konflik occupied/unknown, minimum semua merah dipenuhi lalu ditahan. Mesin tetap running; countdown penahanan null.
- Bila loop tidak memperbarui selama lebih dari 1 detik pada tick default, status menjadi stalled; sinyal dan fase tidak diklaim sebagai keadaan saat ini.
- Respons lama tidak dipakai sebagai keberhasilan baru ketika koneksi gagal. Browser membedakan API hidup dari mesin rusak dan memvalidasi JSON Schema.

Frontend memisahkan loop kesiapan (10 detik), status (500 ms), dan riwayat (2 detik); interval dihitung setelah respons sebelumnya. Tidak ada tick fase atau decrement countdown di frontend. Validasi schema dilengkapi pemeriksaan identitas simpang, keselarasan warna/fase, umur respons, urutan snapshot, dan sesi. Request dibatalkan saat unmount/restart/halaman disembunyikan; hasil terlambat tidak diterapkan pada pemantauan baru. Detail batas kedaluwarsa: [Monitor persimpangan](intersection-monitor.md).

## Database dan lingkungan

Tabel operator_accounts menyimpan UUID, username unik tanpa membedakan huruf besar/kecil, nama tampilan, hash password Argon2id, status aktif, serta timestamp. Akun dibuat secara eksplisit melalui CLI, bukan migrasi atau startup. Tabel operator_sessions menyimpan SHA-256 token sesi acak beserta akun dan batas waktunya. Logout, reset password, serta perubahan status aktif mencabut sesi terkait. Tidak ada password mentah atau token sesi mentah di database.

Browser menerima cookie HttpOnly, SameSite=Strict, dengan Path=/api. Profil dan token CSRF hanya berada di memori halaman; tidak ada token autentikasi dalam localStorage/sessionStorage. Origin/header aplikasi diperiksa untuk login/logout, ditambah token CSRF saat logout. Sesi tidak diperpanjang oleh polling. Detail konfigurasi, pembatasan login, dan batas akses internal ATCS: [Akun dan akses operator](operator-auth.md).

Database URL hanya dibangun di server. Pesan kegagalan API tidak menampilkan kredensial. File .env diabaikan Git dan Docker context; VITE_* hanya untuk konfigurasi publik. Compose membuka port pada localhost. Frontend container memakai Vite untuk pengembangan, belum server produksi.

## Komponen berikutnya

ai_worker/ untuk video/tracking, adaptive_control/ untuk usulan kendali, models/ untuk artefak bobot/metadata, training/ untuk notebook Colab/dataset/evaluasi belum dibuat. Protokol integrasi sudah tersedia pada Tahap 3/4: [alur, batas waktu dan lab terpisah](control-integration.md). Watchdog ada di ATCS; backend/browser tidak mengirim heartbeat pengganti sumber. Adaptif sintetis/EVP pada ruang 2F tidak memiliki jalur perintah ke ATCS utama. Tahap 5 menghubungkan dan mengevaluasi heuristik pada protokol ini. Detail pemisahan eksperimen: [Kendaraan 2E/2F](traffic-simulation.md).

Rincian keputusan timer dan restart: [ATCS fixed-time](atcs-fixed-time.md). Kontrak HTTP: [Kontrak data](contracts.md).
