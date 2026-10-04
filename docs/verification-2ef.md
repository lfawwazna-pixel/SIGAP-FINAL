# Verifikasi SIGAP — Tahap 2E / 2F

Tanggal pengguna: 3 Oktober 2026 (Asia/Jakarta). Hasil diterapkan pada C:\Users\Muhammad Luthfi Fawwazna\Project\PROJECT-SIGAP-ASTRA. Pekerjaan awal disiapkan pada salinan workspace karena izin tulis belum tersedia; setelah akses dibuka, berkas yang berubah disalin ke proyek asli dengan cadangan. .env, akun operator dan data database tidak diganti.

## Hasil akhir pada proyek asli

| Pemeriksaan | Hasil |
|---|---|
| Python/backend | 100 tes lulus, tanpa skip; termasuk PostgreSQL nyata dan proses ATCS/backend terpisah |
| Frontend | 47 tes lulus dalam lima berkas |
| TypeScript dan Vite build | Lulus |
| JSON Schema dan tipe frontend | Pemeriksaan sinkron lulus |
| Database | PostgreSQL Compose hidup; regresi migrasi dan autentikasi nyata lulus |
| Alur HTTP lokal | Login, data ATCS, percobaan, spawn, prioritas, kecepatan, pause, reset dan logout lulus |
| Pemeriksaan visual browser | Belum dilakukan karena pengaturan izin Browser Use tersimpan memblokir localhost |

Satu peringatan deprecation Starlette TestClient/httpx tetap dilaporkan. Tidak ada dependency baru, migrasi database baru atau deployment pada pekerjaan ini. Image aplikasi Compose belum dibangun; aplikasi diverifikasi sebagai proses pengembangan lokal.

## Bukti perilaku kendaraan dan EVP

Tes memeriksa empat rotasi lintasan, ruas masuk yang diperpanjang, berhenti dengan ujung depan sebelum garis henti, larangan masuk pada kuning/merah, penyelesaian kendaraan yang sudah masuk, belok kiri saat lampu merah, yield saat bergabung, keluaran terblokir, spawn tanpa tumpang tindih, jarak aman pada arus campuran, dan pengulangan seed yang konsisten.

Kasus prioritas mencakup ambulans terhadap pemadam yang lebih dekat, dua ambulans berbeda jarak, seri jarak, target yang sudah dilayani saat EVP baru muncul, kuning/semua merah penuh, seluruh EVP selesai, serta pemulihan ke strategi adaptif maupun fixed-time. Prioritas jenis adalah aturan percobaan yang diminta pengguna. Model belum mengevaluasi perilaku lalu lintas atau prioritas darurat lapangan.

Pemisahan diuji pada kelas eksperimen, endpoint dengan akun berbeda, UI ketika berpindah ke/dari simulasi, serta proses ATCS yang tetap hidup setelah backend dihentikan. Perintah percobaan diuji tidak memanggil layanan ATCS; akses anonim, CSRF/origin salah, input di luar batas dan ID percobaan lama ditolak.

## Uji melalui layanan lokal

Alur dijalankan melalui Vite :5173 → backend :8000, PostgreSQL :5432, dan ATCS :8001:

1. GET percobaan anonim menghasilkan 401; akun lokal dapat login.
2. Ruang percobaan direset dan diberi arus otomatis nol, strategi adaptif, kecepatan 3×.
3. Pemadam dari U pada jarak 60 unit, ambulans dari T pada 350 unit, dan ambulans dari S pada 100 unit dimunculkan.
4. Setelah percobaan mulai, ambulans S dipilih: ambulans mendahului pemadam, lalu jarak menentukan pilihan sesama ambulans.
5. Jeda membekukan waktu percobaan. Reset mengganti ID percobaan dan mengosongkan kendaraan.
6. ID sesi ATCS sebelum/sesudah tetap sama; waktu dan nomor snapshot kendaraannya bertambah, kecepatan tetap 1×.
7. Ruang percobaan dikembalikan ke keadaan awal dijeda, strategi adaptif sintetis, arus 10 per arah, semua keluaran terbuka, 1×. Sesi uji logout.

## Batas yang tetap terlihat di produk

- Kendaraan ATCS dan Simulasi adalah data sintetis. SIGAP berbasis CCTV/YOLO belum dapat diaktifkan.
- Adaptif dan EVP sekarang hanya tersedia pada eksperimen terpisah; override/fallback operasional belum dibuat.
- Geometri menggunakan unit skema, bukan meter. Ruas pintas selebar 50 unit menampung mobil selebar 18 unit, dengan selubung jarak konservatif.
- Maksimal 160 kendaraan per dunia, empat eksperimen per backend, satu worker backend/ATCS. Ruang percobaan tersimpan dalam memori dan kedaluwarsa setelah satu jam tanpa pembacaan.
- Tes jsdom memverifikasi struktur, label, interaksi, kontrol, navigasi dan lifecycle data. Hasil tersebut tidak membuktikan tata letak piksel atau kenyamanan visual pada semua ukuran layar.
- Tidak digunakan jalur browser alternatif untuk melewati pembatasan inspeksi visual.

Panduan penggunaan dan aturan lengkap: [Kendaraan dan percobaan](traffic-simulation.md). Implementasi berhenti pada 2E/2F.
