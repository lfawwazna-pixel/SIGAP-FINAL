# Pemeriksaan kendaraan video dan peta — 7 Oktober 2026

Peta menggunakan satu ikon untuk setiap objek pada hasil tracking mutakhir. Pendekat mengikuti kamera U/T/S/B. Objek di luar ROI tetap tampil secara skematis; kebutuhan lampu hanya dihitung dari ROI yang layak. Kalibrasi dan pengambilalihan lampu tidak lagi menjadi syarat untuk menampilkan kendaraan pada ruang kerja SIGAP. Setelah pengambilalihan, ruang kerja ATCS memakai daftar kendaraan video yang sama dan tetap membaca fase aktual dari arbiter ATCS.

## Hasil pemeriksaan

- Backend: 229 tes lolos sebelum perapian shutdown; 38 tes terkait video/adaptif/vision lolos setelahnya. Termasuk tes proses anak asli untuk memastikan pipe dan proses worker ditutup. Tes dengan penanda `postgres` dan `process` tidak termasuk dalam 229 tes tersebut.
- Frontend: 72 tes lolos, pemeriksaan tipe dan kontrak lolos, build produksi berhasil. Konfigurasi sementara `preserveSymlinks` dipakai untuk mengatasi penolakan `realpath` dalam lingkungan pengujian Windows, lalu dihapus. Konfigurasi produksi tetap sama.
- Empat rekaman utama diproses oleh model lokal dengan GPU dan ByteTrack. Jumlah ikon dibandingkan langsung dengan daftar hasil tracking dalam satu snapshot, bukan dengan hitungan manual dari video.

| Sampel | U terlacak / peta | T terlacak / peta | S terlacak / peta | B terlacak / peta |
| --- | --- | --- | --- | --- |
| Empat kamera | 10 / 10 | 6 / 6 | 4 / 4 | 7 / 7 |
| SIGAP aktif | 5 / 5 | 15 / 15 | 5 / 5 | 8 / 8 |
| Decoder Utara berhenti | 0 / 0 | 7 / 7 | 5 / 5 | 9 / 9 |
| Decoder Utara pulih | 1 / 1 | 12 / 12 | 5 / 5 | 6 / 6 |

Saat stabil, throughput teramati sekitar 5 FPS per kamera, sesuai pembatasan decoder. Pengambilalihan SIGAP, fallback ke ATCS setelah decoder Utara dihentikan, serta pemulihan decoder berhasil menggunakan runtime ATCS, pengirim adaptif, decoder, dan worker vision asli. HTTP antarkomponen pengujian memakai transport ASGI dalam satu proses karena akses socket lokal dari sesi pengujian timeout. Ini menguji jalur aplikasi dan mesin kendali, tetapi bukan bukti login PostgreSQL atau verifikasi visual browser secara penuh.

Kalibrasi Utara, Timur, dan Selatan memiliki irisan kecil pada batas lajur tengah. Irisan itu membuat data sesekali tidak layak dan membatalkan aktivasi. Batas lajur tengah disamakan dengan batas lajur tetangganya; poligon outer/inner, garis henti, dan sumber video tetap memakai penandaan operator. Pemeriksaan raster resolusi 2001 × 2001 tidak menemukan irisan interior setelah perbaikan, dan pemeriksaan tracking aktual berikutnya berhasil mengambil alih kendali. Penandaan ini tetap memerlukan evaluasi lapangan/manual; pemeriksaan tersebut tidak mengukur akurasi deteksi atau panjang antrean sebenarnya.

Kalibrasi lama dicadangkan dalam `work/backups/calibration-boundaries-20261007`. Bukti rinci berada di `work/runtime/map-sync-validation-20261007.json`, dan perbandingan gambar pada `work/runtime/calibration-boundaries-review.jpg`. Berkas tersebut lokal dan tidak dikirim ke GitHub. Worker GPU dan proses aplikasi yang dibuat untuk pengujian dihentikan setelah pemeriksaan; PostgreSQL yang dinyalakan operator tidak dihentikan oleh sesi ini.

Video, model, dan metadata kalibrasi adalah aset lokal yang diabaikan Git. Perubahan kode dan laporan ini dapat dibagikan lewat GitHub, tetapi aset lokal perlu disiapkan terpisah pada perangkat lain. Klip ambulans/pemadam serta prioritas EVP berbasis deteksi belum diuji pada pekerjaan ini.
