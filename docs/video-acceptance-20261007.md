# Pemeriksaan empat kamera dan kendali SIGAP — 7 Oktober 2026

## Kesimpulan

Jalur tracking → pengukuran → peta → pengambilalihan lampu, fallback, dan pemulihan otomatis berhasil diuji dengan empat rekaman utama, model lokal, GPU, dan runtime ATCS asli. Ini membuktikan perilaku perangkat lunak pada rekaman tersebut. Akurasi jumlah kendaraan terhadap video sebenarnya belum lulus: pada satu sampel Selatan yang padat, banyak motor terlihat tetapi hanya satu motor terlacak. Tahap 6C belum dapat dinyatakan selesai untuk penggunaan lapangan.

## Perbaikan pada pemeriksaan ini

Jumlah kendaraan di bawah pratinjau SIGAP kini berasal dari hasil tracking yang menyertai JPEG yang ditampilkan, melalui `X-Track-Count`. Sebelumnya angka diambil dari polling status lain sehingga dapat menunjuk frame yang berbeda. Nol hanya ditampilkan bila frame terverifikasi memang memiliki nol track. Respons tanpa metadata jumlah tidak ditebak sebagai nol; frame kedaluwarsa atau dari sumber lama dibuang bersama angkanya. Tes mencakup perubahan jumlah, metadata hilang, dan pergantian sumber.

Peta tetap memakai satu ikon per track pada snapshot pengukuran yang sama. Pendekat mengikuti kamera U/T/S/B; penempatan dalam lajur bersifat skematis. Objek di luar ROI tetap tampil tetapi tidak otomatis menambah kebutuhan hijau. Sinkronisasi ini tidak menjamin bahwa model sudah mendeteksi semua kendaraan fisik. Pratinjau JPEG dan polling peta juga mempunyai waktu pembaruan masing-masing; keduanya bukan satu transaksi render browser.

## Bukti uji

- 52 tes backend terkait video, vision, pengukuran, kontrol, dan adaptif lolos setelah perbaikan.
- 73 tes frontend lolos; pemeriksaan tipe dan build produksi berhasil. Konfigurasi sementara `preserveSymlinks` hanya digunakan pada salinan pengujian karena pembatasan Windows. Konfigurasi proyek produksi tidak diubah.
- 1 tes integrasi PostgreSQL lolos pada database `sigap_test`: migrasi, kredensial salah, login, persistensi sesi, logout, dan pencabutan sesi. Akun operator produksi tidak diubah.
- Sembilan pemeriksaan integrasi GPU/ATCS asli lolos: jumlah track/peta per kamera, kelayakan kalibrasi empat kamera, tampilan tanpa kalibrasi, fase aktual setelah takeover, penghilangan ikon kamera yang gagal, fallback ke ATCS, pengambilalihan otomatis setelah kamera pulih, loop pada EOF sebenarnya, dan pelepasan manual yang tetap pada ATCS.

| Sampel integrasi | U track/peta | T track/peta | S track/peta | B track/peta |
| --- | --- | --- | --- | --- |
| Empat kamera stabil | 10/10 | 9/9 | 5/5 | 6/6 |
| SIGAP mengambil alih | 6/6 | 14/14 | 7/7 | 4/4 |
| Decoder Utara dihentikan | 0/0 | 14/14 | 7/7 | 4/4 |
| Decoder pulih | 13/13 | 16/16 | 9/9 | 4/4 |
| Setelah EOF Utara berulang | 7/7 | 16/16 | 7/7 | 6/6 |

Throughput tracking yang teramati pada sampel stabil: U 5,02; T 4,97; S 4,95; B 4,91 FPS. Decoder memang dibatasi 5 FPS per kamera. Angka ini adalah throughput kamera pada laptop pengujian, bukan klaim inference maksimum, FPS ekspor, atau kinerja perangkat lain.

Saat EOF, identitas sumber tetap sama, generasi tracker berubah, dan pengukuran dibangun ulang; aktivasi dapat pulih setelah data kembali layak. Gangguan kamera tidak meninggalkan ikon lama pada pendekat yang gagal. Pelepasan manual menonaktifkan pemulihan takeover otomatis.

Transport antar aplikasi pada uji integrasi memakai ASGI dalam satu proses karena koneksi ke server yang diluncurkan dari sesi sandbox timeout. Decoder, worker GPU, mesin ATCS, dan pengirim adaptif tetap asli. Uji PostgreSQL memakai koneksi database nyata yang dinyalakan operator. Pemeriksaan ini belum menjadi bukti seluruh alur visual browser; pemeriksaan browser memerlukan peluncuran aplikasi dari terminal operator.

## Akurasi yang masih harus dituntaskan

Empat frame asli dan beranotasi ditinjau secara visual. Sampel Selatan sekitar detik 37,6 menunjukkan antrean motor padat yang sebagian besar tidak dideteksi. Uji model pada frame yang sama, confidence 0,35 dan ukuran inference 640/960/1280, menghasilkan 0/1/0 motor; pengurangan confidence ke 0,1 menghasilkan lebih banyak kandidat tetapi tidak membuktikan akurasi atau menyelesaikan masalah. Pengaturan produksi tidak diubah berdasarkan satu frame ini.

Resolusi lebih tinggi saja belum cukup. Pekerjaan berikutnya adalah anotasi manual frame CCTV lokal yang representatif, pembagian train/validasi berdasarkan klip/waktu, pelatihan perbaikan untuk motor padat, lalu pembandingan jumlah/lajur/antrean dengan ground truth. Waktu tunggu saat ini adalah durasi berhenti yang diamati sejak track muncul, bukan total waktu antre dari sebelum rekaman diamati. Akurasi lajur dan panjang antrean juga belum memiliki pengukuran manual yang tervalidasi.

Klip ambulans/pemadam dan prioritas darurat berdasarkan deteksi tidak diuji pada pekerjaan ini. Rekaman dari lokasi/waktu berbeda adalah masukan prototipe, bukan pengamatan serentak satu persimpangan fisik.

## Artefak dan kondisi setelah pengujian

Bukti lokal disimpan di `work/acceptance/pipeline-report.json`, `resolution-comparison.json`, serta gambar raw/tracking/native setiap kamera. Video, model, metadata, dan bukti gambar lokal tetap diabaikan Git. Tidak ada perubahan pada video utama, model, `.env`, atau akun operator. Proses GPU dan aplikasi yang dibuat oleh pengujian dihentikan; database operator tidak dihentikan.
