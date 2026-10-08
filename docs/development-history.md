# Catatan implementasi historis SIGAP

Status implementasi: Tahap 3/4 selesai pada integrasi tiruan lokal. Penomoran mengikuti tabel yang diluruskan bersama pengguna: 2C monitor, 2D login, 2E kendaraan, 2F kontrol percobaan. Pemeriksaan visual browser masih tertunda karena izin tersimpan. CCTV/YOLO belum terhubung.

| Tahap | Hasil yang dituju | Syarat selesai |
|---|---|---|
| 1 — Spesifikasi | Geometri, arus, baseline, hubungan ATCS–SIGAP | Keputusan tersimpan dan batas asumsi lapangan jelas |
| 2A — Fondasi | Struktur, kontrak, konfigurasi tervalidasi, health API, migrasi awal, layar kesiapan | Build/test lolos; keterbatasan lingkungan dilaporkan |
| 2B — ATCS fixed-time | Mesin fase U–T–S–B, timer mandiri, transisi kuning/semua merah, status dan kejadian | Urutan/durasi benar; countdown bersumber dari ATCS; pengendali tetap hidup tanpa backend/browser |
| 2C — Visualisasi simpang | Peta sesuai geometri, ruas pintas, arah/rambu, tampilan fase | Jalur dan lampu sesuai status; tidak ada fase buatan frontend |
| 2D — Akun dan UI operator | Login, sesi, hak akses; menyambungkan identitas operator ke monitor 2C | Proteksi endpoint dan perilaku UI sesuai akses; akun dibuat eksplisit, tanpa akun bawaan |
| 2E — Kendaraan dan geometri | Jalan lebih panjang, ruas pintas lebih lebar, kendaraan, antrean dan area konflik | Kendaraan mengikuti sinyal, menjaga jarak, memberi jalan dan tidak memasuki keluaran terblokir |
| 2F — Kontrol percobaan | ATCS/SIGAP/Simulasi; jam percobaan terpisah; arus, kontrol waktu, spawn EVP dan heuristik sintetis | Reset/jeda/speed tidak memengaruhi ATCS; prioritas dan transisi diuji; SIGAP CCTV ditandai belum tersedia |
| 3 — Integrasi tiruan SIGAP–ATCS | Status, permintaan override, fase, heartbeat dan pelepasan kendali | Perintah valid diterima; salah, berulang dan kedaluwarsa ditangani |
| 4 — Override dan fallback | Pengambilalihan, timeout, gangguan, transisi dan pemulihan | SIGAP gagal kembali ke ATCS secara aman; pulih menunggu operator |
| 5 — Adaptif dengan data buatan | Mengintegrasikan dan mengevaluasi heuristik percobaan terhadap protokol operasional | Batas waktu, pemerataan pelayanan dan alasan keputusan teruji |
| 6A — Dataset dan pelatihan | Dataset, YOLO26, Colab, evaluasi dan ekspor | Model berversi, data uji terpisah, keterbatasan tercatat |
| 6B — Deteksi/tracking satu pendekat | Video, ROI, hitungan, antrean dan waktu tunggu | Pengukuran dibandingkan pencatatan manual |
| 6C — Empat pendekat | U/T/S/B, waktu dan kualitas sumber | Stream putus/data basi dikenali; inferensi tidak menghambat API |
| 7 — Integrasi AI–kontrol | Pengukuran video menggantikan data sintetis pada jalur operasional | Keputusan memakai data valid; kegagalan memicu fallback |
| 8 — Prioritas darurat operasional | Mengintegrasikan aturan EVP yang diuji di 2F dengan deteksi terverifikasi | Transisi aman, penyelesaian pelayanan dan pemulihan normal/gangguan diuji |
| 9 — Dashboard lengkap | Kamera, evaluasi, kualitas data, riwayat keputusan dan akses | Setiap tampilan memakai data sistem yang tersedia |
| 10 — Evaluasi dan dokumentasi | Fixed-time vs adaptif pada skenario setara; laporan dan panduan | Eksperimen dapat diulang; klaim didukung pengujian |

## Batas Tahap 2A

Tidak membuat mesin fase, animasi kendaraan, login penuh, kendali adaptif, deteksi/tracking, pelatihan, prioritas darurat, atau deployment. Tersedianya kontrak tidak sama dengan tersedianya fitur tersebut.

## Hasil Tahap 2B

1. Mesin fase membaca satu konfigurasi; siklus nominal U-hijau ke U-hijau berikutnya 450 detik.
2. Jam monotonic dan task milik proses ATCS berjalan tanpa polling, backend, atau database.
3. Startup/restart selalu semua merah minimum; ID sesi baru, tidak melanjutkan fase dari memori lama.
4. Input konflik lokal menahan semua merah saat occupied/unknown; default simulasi `assumed_clear` ditampilkan secara jujur.
5. API status dan riwayat kejadian tersedia; riwayat memori dibatasi 1.000 kejadian per sesi.
6. Tes deterministik dan tes dua proses nyata membuktikan urutan serta kemandirian timer.

Rincian: [Pengendali ATCS fixed-time](atcs-fixed-time.md). Peta, kendaraan, login dan integrasi adaptif belum ditambahkan pada tahap ini.

## Hasil Tahap 2C

1. Peta SVG simetris: dua lajur masuk/keluar, median, empat ruas pintas belok kiri, pulau pemisah, garis henti, panah lajur, rambu arah dan beri jalan.
2. Pemilihan pendekat memakai mouse/keyboard, detail lajur, serta toggle rute lurus/kanan; tidak mengirim perintah lampu.
3. Status/countdown hanya dari ATCS; data gagal/basi membuang tampilan lampu aktif. Kuning, semua merah, dan penahanan konflik ditampilkan terpisah.
4. Riwayat aktual dengan filter, pagination, retensi tampilan 100 kejadian, serta pemisahan sesi setelah restart.
5. Layout peta/panel/riwayat memakai IBM Plex, warna abu dingin/biru, dan status melalui teks serta warna. Tata letak kecil memakai susunan vertikal dan area peta/tabel yang bisa digeser.
6. 27 tes frontend, 51 tes Python, build, kontrak, serta sambungan HTTP lokal melalui Vite lolos. Pemeriksaan visual browser belum lolos tahap izin dan tidak diklaim selesai.

Rincian: [Monitor persimpangan](intersection-monitor.md). Kendaraan, login, override, dan AI belum ditambahkan pada pengerjaan 2C.

## Hasil Tahap 2D

1. Login interaktif dengan ilustrasi pendekat U/T/S/B, form aksesibel, tampil/sembunyikan password, indikator Caps Lock, serta penanganan gagal masuk dan layanan putus.
2. Akun PostgreSQL dengan hash Argon2id, cookie sesi HttpOnly, masa berlaku absolut, proteksi origin/CSRF, pembatasan login dan pencabutan sesi saat logout.
3. Seluruh endpoint monitor memeriksa sesi dan izin operator. Akses langsung, reload, tombol kembali, kedaluwarsa dan respons permintaan lama ditangani tanpa membuka monitor sebelum verifikasi.
4. Identitas operator dan menu keluar terhubung ke monitor 2C. Tidak ada hak kendali fase atau pengelolaan akun lewat web pada tahap ini.
5. Akun lokal pertama dibuat sesuai permintaan pengguna. Tidak ada akun/password bawaan dalam migrasi, seed atau frontend. CLI tersedia untuk membuat, menonaktifkan, mengaktifkan dan mereset akun.
6. PostgreSQL nyata kini berjalan; migrasi aplikasi dan database uji terpisah diterapkan tanpa perbedaan skema. Verifikasi database yang tertunda dari 2A telah diselesaikan.
7. 71 tes backend termasuk PostgreSQL nyata dan 40 tes frontend lulus; build, kontrak dan alur HTTP login sampai pencabutan sesi lulus. Pemeriksaan visual browser tetap belum dilakukan karena pengaturan izin tersimpan.

Rincian: [Akun operator](operator-auth.md) dan [hasil verifikasi 2D](verification.md). Mesin fase ATCS tetap tidak membutuhkan database.

## Hasil Tahap 2E / 2F

Empat lengan jalan diperpanjang; ruas pintas kiri diperlebar untuk satu mobil. TrafficWorld berjalan pada proses ATCS dan memasok area konflik. Eksperimen pada backend memiliki jam, kendaraan, statistik, riwayat dan pengendali sendiri. Kontrol waktu/arus/reset serta spawn ambulans/pemadam hanya tersedia pada eksperimen. Heuristik prioritas memilih jenis, jarak, lalu urutan kedatangan; target yang sudah diberi pelayanan diselesaikan sebelum beralih.

Tiga pilihan UI tersedia, tetapi SIGAP CCTV belum dapat diaktifkan. Adaptif sintetis dan EVP percobaan berjalan pada ruang Simulasi. Rincian: [Kendaraan dan percobaan](traffic-simulation.md).

## Hasil Tahap 3 / 4

Protokol observe/activate/heartbeat/plan/release, rahasia antarlayanan, sesi kendali dan revision, tanda terima serta penolakan perintah lama/duplikat diterapkan. ATCS mengawasi data dan heartbeat secara mandiri, menjalankan perpindahan aman dan fallback tanpa reset waktu/run. Pemulihan memerlukan aktivasi operator baru. Dashboard menampilkan kesiapan, tindakan dan riwayat, sementara sumber CCTV tetap belum tersedia. Lab terpisah menguji pengirim mati, frame membeku dengan heartbeat hidup, serta pelepasan manual melalui dua proses nyata.

Panduan: [Integrasi kendali](control-integration.md). Tahap berikutnya **5 — Adaptif dengan data buatan**, dikerjakan setelah instruksi berikutnya; pekerjaan ini tidak melanjutkan pelatihan YOLO atau EVP operasional.
