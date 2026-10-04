# Arsip verifikasi SIGAP — Tahap 2D

Laporan ini merekam hasil sebelum kendaraan/percobaan ditambahkan. Hasil terbaru: [Verifikasi 2E/2F](verification-2ef.md).

Tanggal: 3 Oktober 2026. Lokasi: C:\Users\Muhammad Luthfi Fawwazna\Project\PROJECT-SIGAP-ASTRA. Lingkungan Windows, Python 3.14.7, Node 26.10.0, PostgreSQL 17.11-bookworm melalui Docker Compose.

## Hasil pemeriksaan

| Pemeriksaan | Hasil | Bukti dan batas |
|---|---|---|
| Backend Python | Lolos | 71 passed, tanpa skip; termasuk autentikasi, PostgreSQL nyata, mesin ATCS dan kemandirian proses |
| Frontend | Lolos | 40 tes: kontrak/data, monitor, peta/riwayat, form login, penjagaan sesi dan navigasi |
| TypeScript/build | Lolos | Pemeriksaan tipe dan Vite build berhasil setelah perubahan terakhir frontend |
| Kontrak JSON Schema | Lolos | Export Python --check dan contracts:check frontend sinkron, termasuk SessionView |
| Konfigurasi Compose | Lolos | docker compose config --quiet berhasil dengan konfigurasi autentikasi |
| PostgreSQL dan migrasi aplikasi | Lolos | Container database berjalan; migrasi sampai 0002_operator_sessions, alembic check tanpa perbedaan skema |
| PostgreSQL pengujian | Lolos | Database sigap_test terpisah; migrasi, ORM, autentikasi, sesi lintas instance backend dan pencabutan diuji |
| Alur HTTP layanan lokal | Lolos | Vite :5173 → backend :8000 → PostgreSQL dan ATCS :8001; login, data operator, logout dan penolakan token lama |
| Akun operator lokal | Dibuat | Pembuatan eksplisit sesuai permintaan pengguna; bukan akun seed/startup atau password dalam repository |
| Pemeriksaan visual browser | Tertunda | Browser Use menolak localhost karena pengaturan izin tersimpan, termasuk setelah pengguna memberi izin dalam chat |
| Build image aplikasi/deployment | Belum dilakukan | Database Compose telah dijalankan; frontend/backend/ATCS diuji sebagai proses lokal |

Peringatan deprecation Starlette TestClient/httpx masih muncul pada suite Python. Peringatan tidak disembunyikan dan tidak menggagalkan tes.

## Cakupan autentikasi

Tes unit backend menggunakan database sementara dengan hash Argon2id nyata. Pengujian mencakup endpoint terlindungi, kredensial salah/tidak dikenal/akun nonaktif, cookie, hash sesi, masa berlaku, pencabutan saat logout, rotasi sesi, origin/header/CSRF, pembatasan login, respons validasi tanpa password, kegagalan database, serta pembuatan password pendek yang memerlukan opsi eksplisit.

Tes PostgreSQL memakai database khusus sigap_test, terpisah dari sigap yang menyimpan akun pengguna. Tes menerapkan migrasi dan memeriksa keselarasan ORM, membuat akun pengujian unik, membuktikan sesi dapat dibaca instance backend baru, memeriksa timestamp berzona waktu, logout serta penolakan sesi lama/nonaktif. Pembersihan hanya menghapus akun pengujian miliknya dan memeriksa penghapusan sesi terkait; tidak menghapus database atau akun lain.

Tes frontend membuktikan monitor tidak dirender sebelum sesi terverifikasi, akses langsung ke /monitor kembali ke login bagi pengguna anonim, password dibersihkan setelah dikirim, tidak ada penulisan token ke storage browser, dan kesalahan login/rate limit/layanan/kontrak ditampilkan. Pengujian juga mencakup penolakan permintaan lama, pemeriksaan ulang saat kedaluwarsa, navigasi kembali, logout dengan CSRF, kegagalan logout, serta reload sesudah keluar.

Smoke test HTTP memakai layanan lokal sungguhan. Konfigurasi anonim menghasilkan 401; login menghasilkan 200 dan cookie; session, configuration, health, status dan events menghasilkan 200; logout menghasilkan 204; penggunaan ulang cookie sesi lama menghasilkan 401. Pemeriksaan ini memverifikasi alur jaringan/API, bukan rendering browser.

## Database dan konfigurasi lokal

.env lokal dibuat dengan password PostgreSQL acak dan diabaikan Git/Docker context. Password database tidak ditampilkan atau dimasukkan ke dokumentasi. Akun operator pertama dibuat dengan pilihan kredensial pengguna, tanpa menambahkan password bawaan pada source code, migrasi, seed atau frontend. Database menyimpan hash password dan hash token sesi.

Verifikasi PostgreSQL nyata yang sebelumnya tertunda pada 2A–2C kini sudah diselesaikan. Tidak ada klaim bahwa pengendali ATCS membutuhkan PostgreSQL: proses ATCS tetap berjalan sendiri dan hanya akses operator yang memerlukan database.

## Batas bukti visual dan simulasi

Tes frontend memakai jsdom dan timer terkendali. Tes ini memeriksa perilaku, struktur, label aksesibilitas dan interaksi; bukan bukti posisi piksel, kontras hasil rendering atau kompatibilitas visual browser. CSS menyediakan tata letak desktop/tablet/ponsel dan reduced motion, tetapi pemeriksaan visual responsif belum dilakukan. Tidak digunakan jalur browser alternatif untuk melewati pembatasan izin.

Tes ATCS tetap memeriksa baseline hijau 85/150/95/100 detik, kuning 3 detik, semua merah minimum 2 detik, dengan siklus nominal 450 detik. Tes proses menggunakan konfigurasi sementara berdurasi pendek dan membuktikan pengendali tetap maju ketika backend dimatikan serta tanpa polling. Ini bukti kemandirian proses lokal, bukan integrasi perangkat lapangan atau evaluasi kinerja lalu lintas.

Monitor tetap baca saja. Data sinyal yang tidak tersedia ditampilkan abu-abu dengan countdown —; ini bukan perintah semua merah atau fallback SIGAP. Area konflik masih assumed_clear, tanpa kendaraan, antrean atau pengukuran CCTV. Riwayat ATCS memakai memori 1.000 kejadian dan UI menyimpan 100 kejadian terbaru selama halaman aktif; belum ada riwayat permanen.

Implementasi berhenti pada **2D — Akun dan UI operator**. Berikutnya **3A — Simulasi arus kendaraan**, menunggu instruksi pengguna. Override/heartbeat/fallback SIGAP, YOLO, kontrol adaptif dan deployment belum dikerjakan.
