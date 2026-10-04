# Akun dan akses operator — Tahap 2D

SIGAP memakai sesi acak melalui cookie HttpOnly, dengan bukti sesi tersimpan di PostgreSQL. Tidak ada JWT/token autentikasi di localStorage/sessionStorage, akun seed, atau mode yang melewati pemeriksaan login. Sejak Tahap 3/4, akun operator memiliki izin monitor:read dan control:operate. Nama pengguna admin tetap berperan operator; nama tidak menentukan izin. Aktivasi/pelepasan kendali memerlukan izin, origin, CSRF dan pemeriksaan keadaan ATCS. Protokol antarlayanan memakai rahasia terpisah yang tidak dikirim ke browser; lihat [integrasi kendali](control-integration.md).

## Alur

1. Saat halaman dibuka, frontend memeriksa GET /api/auth/session. Data monitor belum diminta sebelum sesi terverifikasi.
2. Tanpa sesi valid, halaman /login menampilkan formulir. POST /api/auth/login menerima JSON username/password, origin yang diizinkan, dan X-SIGAP-Request: 1.
3. Backend memverifikasi hash Argon2id dan status aktif akun, menghasilkan token acak 32 byte, menyimpan SHA-256 token di database, serta memberi cookie sigap_session. Login ulang mengganti sesi browser lama.
4. Respons profil hanya memuat ID/nama/peran/izin operator, waktu kedaluwarsa, sisa umur sesi, dan token CSRF. Password/hash password tidak dikirim ke frontend.
5. Frontend membuka /monitor. Semua endpoint data SIGAP memeriksa sesi database dan status aktif akun pada setiap permintaan.
6. Logout mengirim token CSRF. Backend menghapus sesi, lalu menghapus cookie. Frontend baru menyatakan berhasil keluar setelah 204 atau setelah sesi sudah dinyatakan tidak valid oleh server.

Akses langsung /monitor, reload, navigasi kembali, pemulihan tab, dan respons 401/403 diuji. Data yang diterima dari permintaan login lama tidak boleh membatalkan sesi baru. Sesi diperiksa ulang maksimum setiap 60 detik, serta pada waktu kedaluwarsa yang dilaporkan server. Polling monitor tidak memperpanjang umur sesi.

## Penyimpanan dan pembatasan

- Password: argon2-cffi 25.1.0, Argon2id; memory_cost 65.536 KiB, time_cost 3, parallelism 4, salt acak. Hash diperbarui setelah login jika parameter berubah.
- Cookie: HttpOnly, SameSite=Strict, Path=/api, tanpa Domain. Secure dapat diaktifkan melalui SIGAP_COOKIE_SECURE; default false hanya untuk HTTP lokal yang digunakan proyek ini.
- Masa sesi: absolut 8 jam secara default, SIGAP_SESSION_SECONDS menerima 60–86.400 detik. Waktu kedaluwarsa divalidasi server; tidak diperpanjang oleh trafik polling.
- Database: operator_sessions menyimpan hash token, operator_id, created_at dan expires_at. Sesi yang kedaluwarsa dibersihkan saat login berikutnya.
- CSRF: origin harus persis masuk allowlist; login/logout membutuhkan header khusus. Logout juga memerlukan token HMAC-SHA256 yang terikat pada token sesi dan diperbandingkan secara konstan. Token CSRF diterima lewat respons sesi dan hanya disimpan dalam memori halaman.
- Login dibatasi per proses: 5 percobaan per nama pengguna, 10 per alamat klien, dan 40 global per 60 detik. Maksimal dua hash password berjalan bersamaan. Ini pembatasan lokal satu proses, belum limiter terdistribusi untuk deployment multiworker.
- Username tidak ditemukan, password salah, dan akun tidak aktif memberi kesalahan kredensial yang sama. Validasi input tidak memantulkan password dalam respons 422. Kesalahan database disamarkan tanpa menampilkan connection string.
- Seluruh respons /api memakai private, no-store. Liveness backend tetap publik; health detail, konfigurasi dan proxy ATCS terlindungi.

ATCS tetap proses internal localhost yang terpisah. Endpoint diagnostiknya belum memakai autentikasi perangkat antarlayanan; frontend hanya mengaksesnya melalui backend. Tahap ini tidak mengklaim keamanan deployment publik atau integrasi ATCS lapangan.

## Pembuatan akun

Migrasi 0002_operator_sessions menambahkan tabel sesi dan indeks username tanpa membedakan huruf besar/kecil. Migrasi tidak membuat akun. CLI backend.app.accounts mendukung create, reset-password, disable, dan enable; input password memakai getpass dan menolak mode terminal yang menggemakan password.

Username dinormalisasi menjadi huruf kecil, panjang 3–80 karakter. Nama tampilan panjang 1–120 karakter. Default pembuatan/reset password meminta 15–128 karakter; opsi --allow-short-password tersedia untuk pilihan eksplisit prototipe lokal. Akun lokal pertama dibuat sesuai permintaan pengguna melalui opsi ini, tanpa menyimpan password pada source code, migrasi atau konfigurasi.

Reset password, menonaktifkan, dan mengaktifkan akun mencabut sesi akun itu sehingga sesi lama tidak kembali berlaku saat akun diaktifkan lagi. Pengelolaan akun dilakukan dari terminal lokal; tidak ada pendaftaran publik atau tautan reset password yang belum memiliki fungsi.

## UI

Login menggunakan IBM Plex, biru baja untuk ilustrasi simpang dan permukaan putih dingin untuk formulir. Pendekat U/T/S/B dapat dipilih untuk menjelaskan arah pada ilustrasi. Ilustrasi diberi label dan tidak berpura-pura menunjukkan kondisi lampu aktual sebelum login.

Formulir menyediakan label permanen, autocomplete, dukungan paste, tombol tampil/sembunyikan password, indikator Caps Lock, status proses, pesan kesalahan yang mendapatkan fokus, serta tombol coba lagi ketika layanan sesi putus. Gerak garis rute/spinner hanya aktif saat verifikasi; prefers-reduced-motion menghentikannya. Pada layar kecil area formulir disusun vertikal.

Nama operator, batas sesi, dan tombol keluar tersedia di menu kanan atas monitor. Sejak 2E/2F, akun juga dapat mengubah ruang percobaan miliknya dengan pemeriksaan origin/CSRF. Sejak 3/4, izin control:operate mengizinkan permintaan aktivasi/pelepasan melalui panel SIGAP setelah syarat pengendali terpenuhi. Perintah eksperimen tetap tidak mengubah fase ATCS utama. [Batas kontrol percobaan](traffic-simulation.md).

## Sumber keputusan teknis

- [Dokumentasi argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/api.html): hash/verifikasi dan pembaruan parameter hash.
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html): penyimpanan hash password.
- [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html): identitas sesi acak, cookie, kedaluwarsa dan pencabutan.
- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html): origin/header/token sebagai lapisan verifikasi permintaan.

Sumber tersebut mendukung pilihan teknis; bukan sertifikasi keamanan aplikasi. Bukti pengujian dan batas pemeriksaan visual dicatat dalam [verifikasi](verification.md).
