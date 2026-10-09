# Susunan kendaraan pada peta — tahap 1, 10 Oktober 2026

Peta video tetap menerima satu entri untuk setiap kendaraan YOLO/ByteTrack yang
diterima oleh penyaring zona. Tahap ini mengubah penempatan ikon di frontend,
tanpa mengubah deteksi, zona, hitungan, antrean, waktu tunggu, atau kendali lampu.

- Motor berbagi satu baris dalam lajur yang sama, maksimal tiga. Satu motor
  diletakkan di tengah; dua berdampingan; tiga berjejer; sisanya memakai baris
  berikutnya. Motor dari pendekat atau lajur berbeda tidak digabung.
- Motor disusun menurut urutan tracking yang stabil dalam kelasnya. Mobil,
  bus, dan truk mempertahankan urutan relatif masing-masing. Posisi ini adalah
  susunan skematis untuk menampilkan jumlah, bukan perkiraan urutan fisik CCTV.
- Mobil sepanjang 26 unit gambar; bus dan truk 52 unit. Motor lebih sempit.
  Jarak antarbaris mengikuti panjang kendaraan, termasuk ruang untuk garis tepi.
- Seluruh identitas tetap ditampilkan. Saat diperlukan, ruas memanjang dalam
  kelipatan 200 unit. Ikon tidak lagi diperkecil khusus karena kepadatan lajur.
  Ukuran tetap mengikuti zoom operator, dan peta dapat digeser.
- Batas peta hanya membesar selama sesi yang sama agar tampilan tidak berubah
  ukuran pada setiap frame; sesi baru memulihkan batas sesuai kebutuhan saat itu.
  Pemanjangan mempertahankan posisi area yang sedang dilihat operator.

Ini menggantikan metode pengecilan ikon padat pada catatan `map-layout-fix-20261007.md`.
Simulasi sintetis mempertahankan posisi dan animasi dari server. Perubahan
perilaku ATCS/EVP dan generator kendaraan campuran belum dikerjakan pada tahap ini.

Verifikasi: 38 tes frontend terkait lulus, termasuk jumlah motor 0/1/2/3/4/5/7/10,
480 kendaraan campuran di dua belas lajur, perubahan kelas, kedatangan baru,
reset sesi, pemanjangan ruas dan kestabilan tampilan, serta regresi monitor dan
simulasi. Typecheck dan build produksi lulus. Pemeriksaan dashboard asli juga
menunjukkan jumlah ikon per pendekat sama dengan tabel, dengan baris motor
berisi satu, dua dan tiga serta bentuk bus/truk yang lebih panjang.
