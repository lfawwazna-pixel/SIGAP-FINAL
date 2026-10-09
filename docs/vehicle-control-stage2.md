# Kendali ATCS, sumber peta dan EVP — tahap 2, 10 Oktober 2026

Sumber kendaraan mengikuti status pengendali ATCS yang terverifikasi, bukan tab
ruang kerja, kesiapan model, atau sekadar tersedianya video.

| Status | Peta ATCS | Peta SIGAP | EVP otomatis |
|---|---|---|---|
| Waktu tetap / aktivasi belum selesai | Ilustrasi acak yang bergerak menurut lampu ATCS | Pratinjau tracking dalam zona | Tanpa notifikasi atau perintah prioritas |
| SIGAP memperoleh kendali | Tracking dalam zona yang sama dengan peta SIGAP | Tracking dalam zona | Konfirmasi baru, lalu transisi aman sebelum hijau prioritas |
| Pelepasan / fallback sedang berlangsung | Sumber tracking dipertahankan sampai status fase kembali waktu tetap | Tracking tersedia | Bukti lokal dan fokus prioritas dihentikan; ATCS menyelesaikan transisi |
| Pelepasan selesai | Kembali ke ilustrasi acak | Pratinjau tracking tetap tersedia | Tidak berjalan |

## Implementasi

- `Monitor.tsx` membaca controller dan mode dari umpan fase yang diverifikasi.
  Saat sumber video digunakan untuk kendali, mode fallback mempertahankan
  tracking sampai ATCS menyatakan kembali ke waktu tetap. Pergantian tab tidak
  mengirim perintah kendali dan tidak mengulang video.
- Ilustrasi ATCS menggunakan dunia kendaraan sintetis yang sudah ada. Polling
  posisi sintetis hanya dilakukan ketika posisi tersebut ditampilkan. Umpan
  fase tetap dipantau pada semua ruang kerja.
- Preview tracking di SIGAP tidak bergantung pada kelayakan pengukuran untuk
  keputusan lampu. Aturan kesegaran dan penyaringan zona tetap berlaku.
- Pengirim adaptif hanya mengumpulkan konfirmasi EVP saat sesi miliknya sudah
  berstatus adaptive dengan controller SIGAP. Bukti sebelum pengambilalihan
  dibersihkan; sesi baru memerlukan konfirmasi baru. Pemantauan YOLO dan tracking
  biasa tetap berjalan sebelum aktivasi.
- Pelepasan operator, penahanan pemulihan otomatis, kehilangan kepemilikan sesi,
  dan gangguan pengirim membersihkan kandidat, target, peristiwa notifikasi,
  status prioritas dan fokus vision lokal.
- Pengawas ATCS menolak perintah prioritas selama pengambilalihan belum selesai,
  termasuk bila pengirim sudah memiliki sesi aktivasi yang valid. Pagar sesi
  tetap menolak perintah setelah pelepasan.
- Notifikasi EVP memerlukan kendali adaptive SIGAP yang tersedia serta kecocokan
  sesi ATCS pada umpan fase. Status aktivasi, fallback, atau kendali tidak
  terverifikasi tidak menampilkan panel prioritas.
- Pelepasan tidak langsung melompati fase. ATCS tetap menyelesaikan minimum
  hijau, kuning, semua merah, dan pemeriksaan area konflik sebelum waktu tetap.

## Verifikasi

57 tes backend terkait dan 62 tes frontend terkait lulus. Tes mencakup deteksi
ambulans saat SIGAP tidak aktif, bukti baru setelah pengambilalihan, penolakan
prioritas pada tahap aktivasi, prioritas yang dikonfirmasi, pelepasan saat EVP
sedang dilayani, penahanan semua merah ketika konflik terisi/tidak diketahui,
perintah sesi lama, sumber peta lintas tab, kesiapan pengukuran, dan kegagalan
polling kendali. Typecheck dan build frontend produksi lulus.

Perubahan tahap ini tidak mengubah generator kendaraan campuran mode simulasi,
rumus analitik, model YOLO, zona kalibrasi, atau susunan motor/bus/truk tahap 1.
Pemeriksaan dashboard asli: ATCS waktu tetap menampilkan ilustrasi; SIGAP
menampilkan preview sebelum pengambilalihan. Setelah aktivasi diterapkan,
peta ATCS berubah menjadi tracking dalam zona dengan tabel hitungan yang sama.
Pelepasan melalui tombol operator diterima dan selesai; ATCS kembali ke waktu
tetap dengan kendaraan ilustrasi serta tanpa panel EVP. Layanan yang dinyalakan
khusus pengujian dihentikan kembali setelah pemeriksaan.