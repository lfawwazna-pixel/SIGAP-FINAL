# Tahap 5 — adaptif data buatan dan sumber video bersama

Implementasi ini menguji pengambilan keputusan adaptif pada prototipe SIGAP–ATCS. Video sudah dapat ditampilkan, tetapi belum diukur oleh YOLO. Dataset, training di Colab, tracking, proyeksi kendaraan ke peta, dan keputusan dari video tetap menjadi Tahap 6–7. Integrasi perangkat lampu lapangan belum tersedia.

## Kendali dan tampilan

ATCS adalah satu-satunya proses yang menerapkan fase lampu. Pengirim adaptif backend membaca pengukuran sintetis, mengirim observasi, heartbeat, dan rencana fase melalui protokol Tahap 3/4. Operator harus mengaktifkan kendali secara eksplisit. Navigasi ATCS/SIGAP hanya mengganti tampilan; kedua tampilan membaca fase, sisa waktu, dan video dari layanan yang sama. Ruang Simulasi memiliki jam dan eksperimen terpisah.

Saat SIGAP sehat dan sudah diaktifkan, ATCS menerapkan rencana adaptif dengan kuning, semua merah, pemeriksaan konflik, serta batas hijau milik ATCS. Saat data tidak layak/kedaluwarsa, komunikasi hilang, atau rencana tidak tersedia, sesi SIGAP dicabut dan ATCS kembali ke fixed-time melalui transisi aman. Pemulihan data tidak otomatis mengambil alih; operator mengaktifkan kembali. Run ATCS tidak direset oleh fallback atau navigasi.

Untuk prototipe lokal, aktifkan kedua nilai pada `.env`, lalu restart backend dan ATCS:

```dotenv
ATCS_ENABLE_TEST_SOURCE=true
SIGAP_ADAPTIVE_SYNTHETIC=true
```

Keduanya default `false` pada contoh/Compose agar sumber buatan tidak diaktifkan tanpa sengaja. Kunci antarlayanan harus valid. Buka SIGAP → **Aktifkan SIGAP dengan data buatan**. Jika sumber belum siap, lihat alasan kesiapan. Uji dropdown **Uji kesehatan pengirim** untuk data membeku, Utara tidak valid, atau pengirim berhenti. Pengirim berhenti memutus data dan heartbeat sekaligus; alasan pertama dapat berupa `DATA_UNUSABLE` karena pengawas data diperiksa lebih dahulu.

## Kebijakan adaptif

Parameter ada di `configs/adaptive-policy.json`; restart layanan setelah mengubah file. Pengirim utama selalu mengikuti batas hijau dan kesegaran yang diberikan ATCS. UI menampilkan nilai efektif. Default:

| Komponen | Aturan |
|---|---|
| Skor | `4 × antrean + 1 × tunggu terlama + 0,5 × usia pelayanan` |
| Durasi | `10 + 2 × antrean + 0,5 × kendaraan terkontrol yang belum mengantre`, dibatasi 10–60 detik |
| Pemerataan | Setelah usia pelayanan 120 detik, dahulukan pendekat yang paling lama belum dilayani dan masih memiliki kebutuhan serta keluaran terbuka |
| Pengulangan arah | Hindari arah yang baru dilayani jika arah lain memenuhi syarat |
| Arus kosong | Pelayanan minimum bergilir pada keluaran yang tersedia |
| Data tidak layak | Tidak membuat rencana fase; pengawas ATCS menangani fallback |
| Semua keluaran penuh | Tidak memaksakan hijau; rencana ditahan |
| Ruas pintas kiri | Dicatat terpisah; tidak menaikkan kebutuhan hijau |

Usia pelayanan dihitung sejak hijau benar-benar diterapkan, bukan sejak rencana diterima. Target 120 detik adalah prioritas pemerataan, bukan jaminan waktu maksimum ketika konflik, keluaran terblokir, atau EVP terjadi. Waktu tunggu adalah akumulasi waktu berhenti kendaraan yang masih mengantre dalam model, bukan hasil pengukuran kamera.

Kontrak pengukuran mencakup ID simpang, sesi sumber, sequence, waktu pengamatan, validitas, jumlah kendaraan terkontrol, antrean, tunggu, arus pintas, dan ketersediaan keluaran untuk U/T/S/B. Data berulang tidak dapat menjadi segar hanya dengan timestamp baru. Riwayat 100 rencana beserta input, skor, alasan dan status disimpan dalam memori backend; restart menghapus riwayat tersebut. Penyimpanan laporan jangka panjang belum menjadi bagian tahap ini.

Simulasi menggunakan kebijakan yang sama. EVP menangguhkan keputusan normal; logika ambulans/pemadam yang sudah ada tetap berlaku. Sesudah pelayanan EVP selesai, keputusan adaptif dihitung ulang dari keadaan terkini. EVP operasional dari deteksi video belum dipasang.

## Video bersama

1. Pada panel **CCTV & rekaman**, pilih U/T/S/B.
2. Unggah MP4 maksimal 256 MiB; setiap pendekat menyimpan satu rekaman aktif.
3. Klik **Jalankan video**. Rekaman diberi label rekaman, bukan siaran langsung. Video tidak berulang otomatis ketika selesai.
4. Jeda rekaman untuk penandaan: gambar poligon 3–12 titik untuk lajur kiri, tengah, kanan, lalu 2 titik garis henti. Simpan. Koordinat dinormalisasi terhadap gambar video.
5. Berpindah ATCS/SIGAP tidak memulai decoder baru atau mengulang rekaman. Mengganti sumber membuat sesi baru dan menghapus penandaan lama. Mengulang rekaman membuat sesi baru dengan penandaan yang sama.

Untuk CCTV langsung, administrator mengisi `SIGAP_CAMERA_URLS` pada server dengan pemetaan JSON U/T/S/B ke URL RTSP atau HTTP(S) yang dapat dibaca FFmpeg. Contoh **placeholder**, bukan kamera yang tersedia:

```dotenv
SIGAP_CAMERA_URLS={"U":"rtsp://CAMERA_HOST/STREAM_PATH"}
```

Restart backend lalu klik **Hubungkan CCTV langsung**. URL/kredensial tidak dikirim ke frontend. Alamat halaman web/player CCTV bukan otomatis URL stream. Kamera nyata belum diuji karena belum ada sumber pengguna yang diberikan. Unggahan dan kalibrasi disimpan pada `work/media` (volume `sigap_media` di Compose); tidak masuk Git. Setelah restart, sumber dan penandaan dipulihkan dalam keadaan siap; operator menjalankan video kembali.

Satu decoder per pendekat menghasilkan preview JPEG 640 piksel lebar, 5 fps, tanpa audio. Setiap frame memiliki `source_session` dan `frame_id`. ATCS dan SIGAP membaca frame/sesi yang sama; perbedaan latensi jaringan antarklien tetap mungkin. Frame yang tidak diperbarui lebih dari 3 detik ditandai tidak mutakhir dan tidak disajikan sebagai frame aktif. Frame rekaman yang dijeda boleh tetap ditampilkan dengan status jeda.

Video berjalan di server, tidak mengikuti tab browser. Perintah video dibagikan kepada semua operator. Akses frame memerlukan sesi login, sementara unggah/putar/jeda/kalibrasi memerlukan izin kontrol dan CSRF. Jalankan backend satu worker selama pengendali/sesi video masih berada dalam memori proses.

Pada tahap ini gangguan video hanya mengubah status video. Pengendali adaptif masih memakai **data buatan**, sehingga gangguan video tidak diklaim sebagai gangguan sumber keputusan. Pada Tahap 7, provider pengukuran harus dikaitkan ke frame video/tracking yang valid; saat itulah kehilangan video/deteksi memicu fallback sumber tersebut. Kotak deteksi, angka kendaraan hasil YOLO, serta gerakan peta berdasarkan kamera tidak dipalsukan.

Penandaan lajur/garis henti mempersiapkan ROI untuk deteksi. Kalibrasi perspektif, konversi jarak meter, validasi tumpang tindih poligon, dan pemetaan lintasan ke peta masih harus diselesaikan bersama tracking. Saat ini server memeriksa jumlah titik, batas koordinat, luas minimum, dan panjang garis henti.

## Evaluasi berulang

```powershell
.\.venv\Scripts\python.exe -m adaptive.evaluate
```

Hasil: [JSON](evaluation-stage5.json), [CSV](evaluation-stage5.csv). Tiga skenario (seimbang, timpang, perubahan arah padat), masing-masing seed 7 dan 29. Durasi kedatangan 900 detik, drain maksimum 450 detik, langkah 0,1 detik. Kendaraan mulai dari kondisi kosong dan semua merah. Seluruh niat kedatangan, lajur awal, tujuan, kecepatan, dan titik pindah lajur dibuat lebih dahulu; hash trace sama untuk pasangan fixed-time/adaptif.

| Skenario | Seed | Rata-rata berhenti fixed/adaptif (detik) | Ditolak di batas masuk fixed/adaptif |
|---|---:|---:|---:|
| Seimbang | 7 | 84,88 / 27,47 | 8 / 8 |
| Seimbang | 29 | 108,26 / 28,48 | 9 / 4 |
| Timpang | 7 | 90,11 / 24,42 | 43 / 22 |
| Timpang | 29 | 91,15 / 18,88 | 46 / 21 |
| Perubahan arah padat | 7 | 109,02 / 22,73 | 69 / 21 |
| Perubahan arah padat | 29 | 107,67 / 20,24 | 70 / 21 |

Semua kendaraan yang diterima selesai melintas sebelum batas drain pada enam pasangan ini. Waktu berhenti mengecualikan kendaraan yang gagal masuk. Karena jumlah penolakan berbeda, hasil tunggu harus dibaca bersama jumlah diterima/ditolak dan sisa kendaraan. Model dapat mengubah tujuan ketika celah pindah lajur tidak tersedia, mengikuti aturan redesain sebelumnya. Hasil ini hanya menunjukkan perilaku pada model sintetis; bukan estimasi manfaat lalu lintas Bandung.

## Validasi

Hasil pengerjaan: 218 tes Python lulus, 1 tes integrasi PostgreSQL khusus dilewati karena database pengujian terpisah belum disiapkan; 67 tes frontend lulus. Kontrak, lockfile, konfigurasi Compose, typecheck, dan build frontend lolos. Pengujian HTTP pada layanan lokal dengan PostgreSQL yang berjalan juga berhasil: aktivasi adaptif, fase SIGAP diterapkan oleh ATCS, data membeku memicu `DATA_UNUSABLE`, lalu pulih ke fixed-time dengan run ATCS yang sama dan tetap memerlukan aktivasi operator. Bukti lokal tersimpan di `work/stage5-live/smoke.json`. Tidak ada video contoh yang dipasang sebagai CCTV pengguna.

Pengujian mencakup batas hijau, antrean/tunggu, pemerataan, keluaran terblokir, data basi, pengirim berhenti, aktivasi ulang manual, autentikasi/CSRF, shared frame identity, frame basi, persistence, dan decoder MP4 nyata. Pengujian frontend mencakup navigasi tanpa perintah kendali, countdown adaptif sama di ATCS/SIGAP, gate sumber buatan, pergantian sesi, serta akses baca saja.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m contracts.export_schemas --check
npm.cmd run contracts:check --prefix frontend
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
```

Pemeriksaan visual browser belum dilakukan pada pengerjaan ini karena akses Browser Use ke localhost ditolak oleh preferensi izin yang tersimpan. Uji DOM dan build tidak menggantikan pemeriksaan visual tersebut.

Decoder memakai [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) dan opsi proses dari [dokumentasi FFmpeg](https://ffmpeg.org/ffmpeg.html).
