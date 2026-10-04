# Spesifikasi SIGAP — Tahap 1

SIGAP — Sistem Pengaturan Fase Lampu Adaptif Berbasis CCTV dan Deteksi Kendaraan YOLO.

Status dokumen: keputusan dasar proyek. Implementasi sudah mencakup fondasi 2A, pengendali fixed-time 2B, visualisasi simpang 2C, akun/UI operator 2D, serta kendaraan dan percobaan terpisah 2E/2F. Integrasi override/fallback SIGAP operasional dan AI masih perilaku tujuan.

## Lokasi dan batas representasi

Acuan lokasi adalah Simpang Ibrahim Adjie–Soekarno Hatta, Kircon, Bandung. Utara/Selatan mengikuti Jl. Ibrahim Adjie; Timur/Barat mengikuti Jl. Soekarno Hatta. Bentuk jalan, lajur, ruas pintas dan rambu adalah penyederhanaan simulasi berdasarkan gambar yang disepakati, bukan survei ukuran atau inventaris rambu lapangan.

Satu sumber konfigurasi yang digunakan aplikasi berada di `configs/intersection.json`. Backend dan ATCS memvalidasi file yang sama saat mulai. Frontend mengambil identitas dari API; tidak menyimpan salinan waktu lampu sendiri. Perubahan konfigurasi membutuhkan restart layanan pada tahap ini.

## Geometri dan gerakan

- Empat lengan, lalu lintas sisi kiri, masing-masing tiga lajur masuk dan tiga lajur keluar, dengan median (revisi sebelum Tahap 5).
- Empat ruas pintas belok kiri terpisah dengan pulau pemisah. Percabangan berada sebelum garis henti; bergabung kembali setelah simpang.
- Mendekati percabangan, lajur kiri khusus menuju ruas pintas, tengah untuk lurus, kanan untuk belok kanan. Kendaraan boleh mulai dari lajur mana pun, lalu berpindah satu lajur setiap manuver di zona persiapan hulu.
- Gerakan belok kiri melalui ruas pintas tidak menunggu lampu, tetapi wajib memberi jalan saat bergabung dan tidak boleh menembus kendaraan lain.
- Gerakan lurus dari lajur tengah dan belok kanan dari lajur kanan mengikuti lampu. Warna biru menunjukkan jalur gerak, bukan izin bebas lampu untuk lurus.
- Jarak depan/belakang, reservasi kedua lajur selama perpindahan dan pemeriksaan lintasan gerak mencegah kendaraan saling memotong. Manuver diselesaikan sebelum percabangan; tidak ada pindah lajur di tikungan.
- Tidak ada putar balik atau perpindahan lajur di tengah simpang. Kendaraan yang sudah masuk menyelesaikan gerakannya; kendaraan baru tidak masuk jika ruang keluar terblokir.

| Asal | Nama jalan | Kiri melalui ruas pintas | Lurus | Kanan |
|---|---|---|---|---|
| U | Ibrahim Adjie | T | S | B |
| T | Soekarno Hatta | S | B | U |
| S | Ibrahim Adjie | B | U | T |
| B | Soekarno Hatta | U | T | S |

Rambu konseptual untuk tahap visual: petunjuk lajur sebelum percabangan, panah lurus/kanan, garis henti pada jalur bersinyal, serta rambu memberi jalan pada titik gabung ruas pintas. Penempatan tersebut adalah aturan simulasi, bukan klaim legal atau kondisi rambu aktual.

## Baseline waktu tetap

Urutan simulasi: **U → T → S → B → U**. Satu pendekat bersinyal aktif pada satu waktu; belok kiri menggunakan ruas pintas terpisah.

| Pendekat | Hijau | Kuning sesudah hijau | Semua merah minimum |
|---|---:|---:|---:|
| U | 85 detik | 3 detik | 2 detik |
| T | 150 detik | 3 detik | 2 detik |
| S | 95 detik | 3 detik | 2 detik |
| B | 100 detik | 3 detik | 2 detik |

Siklus nominal: `(85 + 150 + 95 + 100) + 4 × (3 + 2) = 450 detik`.

Semua merah dapat diperpanjang sampai area konflik kosong. Karena itu 450 detik bukan jaminan durasi setiap siklus. Pergantian ke pendekat berikutnya harus menunggu penyelesaian fase transisi.

Sumber durasi hijau: [penelitian Polban 2025, Tabel 7](https://jurnal.polban.ac.id/proceeding/article/view/6701/4025). Angka digunakan sebagai baseline penelitian, **bukan konfigurasi ATCS terkini yang sudah dikonfirmasi**. Urutan U–T–S–B dan aturan transisi adalah keputusan simulasi proyek; tidak diklaim seluruhnya berasal dari penelitian.

## Hubungan ATCS dan SIGAP

ATCS adalah pengendali mandiri, berjalan sebagai proses terpisah. Mode dasarnya fixed-time. SIGAP kelak mengirim permintaan override; keputusan fase tetap dieksekusi dan divalidasi oleh ATCS.

ATCS nantinya memiliki timer dan pengawas heartbeat sendiri. Hilangnya SIGAP/backend atau data kendali yang tidak layak harus memicu fallback ke fixed-time melalui transisi aman. Fallback tidak boleh bergantung pada browser, database, atau proses SIGAP yang sedang gagal.

Sesudah gangguan pulih, SIGAP kembali berstatus siap dan menunggu pengaktifan operator. Pemulihan koneksi tidak langsung mengaktifkan kembali override. Rincian protokol heartbeat, masa berlaku perintah, transisi, dan pemulihan dibuat dan diuji pada tahap integrasi berikutnya.

## Input dan output tujuan

| Bagian | Input | Output |
|---|---|---|
| ATCS | Konfigurasi, waktu simulasi; kelak permintaan kendali | Fase, pengendali, mode, sisa waktu, kejadian |
| Deteksi kendaraan | Video/CCTV, model hasil pelatihan | Deteksi, tracking, agregat per pendekat dan kualitas data |
| Kontrol adaptif | Agregat kendaraan, status ATCS, batas pengaturan | Usulan fase/durasi beserta alasan |
| Web operator | Status layanan dan kendali, input operator | Pemantauan dan permintaan tindakan yang divalidasi backend |

Pelatihan YOLO direncanakan di Google Colab. `ai_worker/`, `adaptive_control/`, `models/`, dan `training/` adalah bagian tahap berikutnya. Tidak ada layanan AI, model terlatih, atau streaming CCTV aktif sampai Tahap 2F.

## Kejujuran status sampai Tahap 2F

API hidup berbeda dari database terhubung, migrasi siap, dan mesin fase operasional. ATCS sekarang menjalankan timer mandiri dan mengirim fase, sinyal keempat pendekat, sisa waktu, waktu simulasi, nomor pembaruan, serta ID sesi. Startup/restart dimulai dengan semua merah minimum, kemudian urutan resmi dari konfigurasi.

Login dan akses monitor memerlukan akun aktif serta sesi valid di PostgreSQL. Jika database gagal, monitor tidak memperoleh akses alternatif; pengendali ATCS tetap berjalan. Ilustrasi simpang pada halaman login diberi label ilustrasi dan tidak menampilkan klaim status lampu aktual sebelum autentikasi.

Area konflik kini dibaca dari kendaraan sintetis TrafficWorld pada proses ATCS dan diberi sumber `provider`. Ini keadaan model kendaraan, bukan pengamatan CCTV. Provider khusus juga diuji dengan kondisi clear/occupied/unknown. Ketika semua merah ditahan setelah minimum berakhir, `remaining_seconds` bernilai `null`: waktu pelepasan belum diketahui. Riwayat mencatat alasan penahanan dan pergantian.

`observed_at` adalah waktu pembacaan; `updated_at` adalah waktu pembaruan mesin. GET status tidak menggerakkan timer. Jika pembaruan berhenti, API melaporkan unavailable dan tidak mengklaim sinyal lama masih berlaku. Rincian implementasi ada di [Pengendali fixed-time](atcs-fixed-time.md).
