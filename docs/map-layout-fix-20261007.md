# Penempatan kendaraan pada peta SIGAP

Peta CCTV menampilkan satu ikon untuk setiap kendaraan terlacak yang masih mutakhir,
pada pendekat kameranya. Ikon disusun per lajur untuk menunjukkan keberadaan dan
jumlah kendaraan; posisinya bukan proyeksi koordinat kamera atau lintasan fisik
melalui persimpangan. Rekaman yang independen tidak cukup untuk menyimpulkan
lintasan bersama yang bebas konflik. Simulasi sintetis tetap memakai animasi rute.

## Penyebab dan perbaikan

- Urutan lama mengikuti jarak dari bounding box pada setiap sampel. Perubahan
  kecil membuat kendaraan saling bertukar urutan. Slot sekarang diurutkan menurut
  identitas tracking, sehingga perubahan kotak tidak membuat ikon saling menyalip.
- Pengepakan lama hanya menjamin pusat ikon berbeda, bukan seluruh bodinya.
  Jarak normal sekarang 36 unit untuk bodi 26 unit. Jika lajur sangat padat, bodi
  dan garis tepinya diperkecil mengikuti jarak slot. Seluruh identitas tetap tampil.
- Posisi kendaraan lama menduplikasi angka geometri. Posisi baru mengambil pusat
  lajur, awal jalan, garis henti, percabangan, dan pusat rotasi dari
  `configs/map-geometry.json`, dengan ruang untuk seluruh bodi dan margin 6 unit.
- Pergantian lajur tampilan memerlukan tiga sampel tracking baru berturut-turut.
  Membaca ulang satu frame tidak menambah suara. Histeresis ini hanya untuk gambar;
  jumlah untuk pengendali langsung menggunakan klasifikasi sampel terkalibrasi.
- Perubahan susunan CCTV diperbarui serentak. Tidak ada animasi garis lurus yang
  membuat ikon melintasi kendaraan lain, median, pulau, atau lajur yang berbeda.
  Tidak dibuat perjalanan tambahan atau kendaraan buatan untuk mengisi peta.
- Lampu digambar di atas lapisan kendaraan. Badge jumlah per pendekat ditempatkan
  di luar badan jalan. Nomor internal panjang tidak lagi muncul di atas ikon EVP
  dari video; tanda ambulans/pemadam dan penjelasan tooltip tetap tersedia.
- Tabel jumlah memakai lebar kolom yang mengikuti panel dan judul yang dapat
  membungkus. Aturan tabel riwayat tidak diubah.

Kalibrasi tetap menentukan kebutuhan lampu, antrean, dan waktu tunggu. Kendaraan
di luar ROI atau yang sudah melewati garis henti tetap terlihat dalam jumlah
tracking. Tooltip kendaraan yang melewati garis henti menjelaskannya. Slot tersebut
tidak berarti kendaraan kembali mengantre. Data kedaluwarsa, pergantian sumber,
dan reset tracker tetap mengikuti aturan mutakhir dan sesi yang sudah ada.

## Verifikasi

- 67 tes backend untuk geometri, pengukuran video, tracking, dan kendali lulus; mencakup keempat arah,
  tiga lajur, seluruh bodi di dalam jalan, identitas stabil saat kotak bergeser,
  180 objek, penghapusan objek, histeresis tanpa menunda data kendali, reset sumber,
  pergantian loop, data kedaluwarsa, serta objek di luar ROI/melewati garis henti.
- 76 tes frontend lulus; mencakup ukuran bodi beserta stroke, semua 180 ikon tetap
  ada, pembaruan susunan serentak, badge jumlah, marker EVP, lampu, zoom, animasi
  sintetis, jumlah ATCS/SIGAP, login, dan penghentian polling sintetis saat tak dipakai.
- Pemeriksaan kontrak, typecheck, dan build produksi lulus. Tidak ada perubahan
  kontrak API, model YOLO, media, kredensial, atau aturan fase/fallback.
- Pratinjau dibuat langsung dari komponen peta memakai metadata tracking tersimpan
  pada pengujian sebelumnya: U=9, T=6, S=7, B=7; total 29. Tidak ada inferensi baru.
  PNG/SVG/HTML tersedia di `work/map-layout/`; lampu pratinjau berstatus tak diketahui.
- Pengujian langsung dengan GPU/video berjalan tidak dilakukan dalam perbaikan ini.
  Tes kendali sempat tertahan pada inisialisasi socketpair internal Windows; setelah
  akses jaringan lokal diberikan, seluruh 67 tes backend termasuk kendali lulus.
  Browser tidak dapat terhubung ke server pratinjau lokal dari sesi terisolasi ini;
  pratinjau SVG/PNG diperiksa melalui render komponen dan metadata aslinya.

Pemasangan memakai daftar hash, cadangan sumber dan build, serta pemulihan bila
pemeriksaan/build gagal. Pemasang tidak menyalakan SIGAP, database, atau GPU.
