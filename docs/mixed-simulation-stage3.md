# Kendaraan campuran pada mode simulasi — tahap 3, 10 Oktober 2026

Mode Simulasi menggunakan dunia kendaraan campuran. Perubahan ini tidak
mengaktifkan kendali SIGAP, mengubah tracking YOLO/zona, atau mengubah analitik.
Dunia kendaraan ATCS utama tetap menggunakan konfigurasi ilustrasi sebelumnya.

## Kemunculan otomatis dan manual

- Jenis biasa diacak dengan peluang awal: motor 45%, mobil 45%, bus 5%, truk 5%.
  Ini peluang setiap permintaan kedatangan, bukan kuota jumlah pada suatu frame;
  masuk yang penuh tetap menolak kemunculan sampai ada ruang aman.
- Setiap pendekat memiliki jam kedatangan acak sesuai arus kendaraan per menit.
  Tujuan biasa dipilih acak: kiri 25%, lurus 55%, kanan 20%. Mobil dapat berpindah
  lajur di hulu sesuai aturan yang sudah ada; motor, bus, dan truk memasuki lajur
  sesuai tujuan. Tujuan yang tidak dapat dicapai saat pindah lajur tetap mengikuti
  gerakan sah dari lajur saat ini.
- Ambulans dan pemadam tidak termasuk generator otomatis. Tombol manual dan
  endpoint spawn tetap hanya menerima kedua jenis darurat tersebut. Kendaraan
  darurat masuk dari ujung belakang, berjalan lurus, dan memakai aturan EVP
  percobaan yang sudah ada.
- Kandidat EVP dan notifikasi kendaraan sudah dilayani sekarang secara eksplisit
  memilih ambulance/fire_engine; motor, bus, dan truk tidak dianggap EVP.
- Seed tetap memungkinkan pengulangan percobaan; reset mempertahankan seed dan
  pengaturan percobaan serta mengembalikan keadaan dijeda.

## Ukuran dan gerak

Dimensi skematis disimpan di `configs/vehicle-dimensions.json`: motor 22×10,
mobil 26×18, bus/truk 52×20, ambulans 30×18, pemadam 26×18. Frontend memakai
salinan yang diperiksa melalui `npm run contracts:check`, sehingga ukuran ikon
sesuai ukuran bodi pada perhitungan simulasi. Nilai ini unit gambar, bukan meter
atau hasil pengukuran kendaraan di lapangan.

- Celah mengikuti kendaraan dihitung dari panjang setengah bodi kedua kendaraan
  ditambah 8 unit. Bus/truk memerlukan ruang antrean sepanjang dua bodi mobil.
  Bumper depan masing-masing jenis berhenti di belakang garis henti saat merah
  atau kuning; badan panjang juga menahan area konflik lebih lama.
- Motor memakai tiga posisi melintang dalam lajur 40 unit, yaitu -14, 0, +14.
  Jumlah kemunculan tetap satu kendaraan per kedatangan, tanpa menambah motor
  untuk memenuhi baris. Motor berikutnya memakai posisi yang tersedia; bila
  tiga posisi terisi, motor baru harus menunggu atau mengantre di belakang.
- Posisi melintang mengikuti arah lintasan ketika berbelok. Ruang samping
  memberi kesempatan motor sejajar untuk mulai berputar tanpa saling mengunci.
- Mobil, bus, dan truk menahan motor di belakang apabila bodinya memakai bagian
  lebar lajur yang sama; motor tidak melewati ekor bus melalui slot samping.
- Pemeriksaan gerak memakai kotak bodi yang berputar bersama heading, celah depan
  dan samping, serta beberapa sampel lintasan dalam setiap langkah waktu yang
  kecil. Apabila langkah penuh belum aman, gerak dibatasi ke bagian yang aman.
  Tidak ada pemindahan kendaraan oleh tata letak frontend pada mode simulasi.
- Reservasi pindah lajur, jarak mengikuti, batas keluaran, dan deteksi konflik
  memperhitungkan panjang kendaraan dalam mode campuran. Keluaran terblokir
  tetap menahan kendaraan; ruas pintas mempertahankan aturan beri jalan.
- Mulai/jeda, kecepatan, lampu, dan riwayat tetap memakai jam percobaan terpisah.
- Saat arus padat atau kecepatan 3×, mesin memberi kesempatan pembacaan dashboard
  dan perintah operator di antara langkah fisika 0,05 detik. Setiap pemeriksaan
  gerak/transisi selesai sebelum langkah berikutnya; jeda dan reset menghentikan
  sisa langkah percobaan lama.

## Verifikasi

152 tes lalu lintas/simulasi terkait dan 57 tes kendali/EVP lulus. Uji mencakup
bumper enam jenis pada empat arah, antrean di belakang bus/truk, motor berjejer
serta baris berikutnya, belokan motor pada tiga tujuan di empat arah, kapasitas
keluaran, larangan EVP otomatis, start/pause/reset, dan pengujian tiga seed arus
campuran hingga seluruh kendaraan selesai setelah arus dimatikan. Regresi
pindah lajur, keluaran terblokir, lampu, pelepasan kendali, dan EVP manual lulus.

38 tes frontend terkait lulus, termasuk rendering empat jenis biasa, tombol EVP
manual, sumber peta tahap 2 dan susunan motor tahap 1. Pemeriksaan sinkronisasi
kontrak/dimensi, typecheck, dan build frontend produksi lulus.

Uji pada dashboard produksi lokal: pada kecepatan 3× dan arus masuk 10–20
kendaraan/menit per pendekat, terlihat 44 motor, 44 mobil, 5 bus, dan 3 truk
pada waktu percobaan 287,1 detik, tanpa kandidat EVP. Jeda menghentikan jam
percobaan. Peta memperlihatkan baris motor sejajar dan bodi bus/truk yang lebih
panjang. Tombol manual berhasil menambah ambulans dan pemadam; kedua kendaraan
muncul sebagai kandidat EVP, sedangkan permintaan pada ujung masuk penuh
ditolak dengan pesan ruang aman. Screenshot peta disimpan sebagai bukti uji.
Riwayat uji manual juga memperlihatkan ambulans dilayani lebih dahulu, pemadam
berikutnya, transisi kuning/semua merah, lalu kembali ke strategi adaptif
setelah seluruh EVP selesai. Layanan lokal yang dinyalakan untuk uji kemudian
dihentikan kembali; perubahan sumber dan build tersimpan.
