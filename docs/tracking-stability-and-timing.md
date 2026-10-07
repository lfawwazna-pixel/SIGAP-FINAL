# Stabilitas tracking, durasi video, dan arsip kejadian

Perbaikan 7 Oktober 2026 diterapkan pada project lokal. Layanan aplikasi, decoder video, dan GPU dihentikan selama pengerjaan; perubahan berlaku pada startup berikutnya.

## Penyebab dan perbaikan peta

Sebelumnya, daftar kendaraan langsung diganti setiap sampel tracking dan bisa kosong ketika polling gagal sesaat. Kendaraan kecil, tertutup, atau berada di batas gambar dapat terlewat oleh detektor; perubahan ID ByteTrack juga membuat ikon hilang lalu muncul kembali. Daftar sintetis ATCS dan daftar video SIGAP membuat pergantian mode terlihat berbeda.

- `vision/stability.py` mempertahankan posisi terakhir kendaraan yang benar-benar pernah terdeteksi, paling lama **1,2 detik waktu sumber video**. Kotak sementara diberi tanda `~`; ini bukan deteksi baru atau posisi gerak yang diprediksi.
- ID baru hanya disambungkan ke kendaraan hilang yang cocok kelasnya, memiliki overlap kuat dan tidak ambigu. Kendaraan yang masih terlihat tidak digabungkan satu sama lain. Status setiap kamera dan sesi tracker terpisah.
- Daftar stabil yang sama dipakai untuk kotak video, jumlah tracking, pengukuran, dan ikon peta. Peta ATCS dan SIGAP memakai pengamatan yang sama ketika sumber video aktif; overlay deteksi tampil pada mode SIGAP.
- Polling gagal sesaat mempertahankan snapshot terakhir dengan timestamp asli. Data kamera lebih tua dari **3 detik** tetap dibuang dan tidak dipakai untuk keputusan. Sampel kosong yang berhasil, pergantian sumber, dan reset tetap diproses.
- Posisi peta tetap skematis: satu ikon per track, urutan ID stabil dan perpindahan lajur memakai hysteresis. Kotak yang ditahan tidak menciptakan bukti gerakan berhenti baru.

Retensi singkat mengurangi kedip; tidak menjamin identitas sempurna ketika kendaraan lama tertutup. Penempatan lajur memerlukan kalibrasi. Jumlah kendaraan di luar pandangan kamera masih tidak diketahui.

## Durasi hijau yang konservatif untuk video

Rumus sebelumnya hanya memakai kendaraan terdeteksi dan membatasi hijau adaptif maksimal 60 detik. Lima kendaraan antre bisa menghasilkan 20 detik walaupun waktu dasar Timur 150 detik dan antrean di belakang tidak terlihat.

Sumber CCTV/rekaman kini memakai waktu dasar setiap pendekat dari konfigurasi persimpangan:

| Kondisi | Batas durasi |
|---|---|
| Pandangan antrean sebagian, bawaan | Minimal 75% waktu dasar |
| Antrean berhenti mencapai batas hulu area, area kotak kendaraan ≥35%, atau ≥3 kendaraan antre menunggu ≥20 detik | Minimal waktu dasar penuh |
| Penurunan dibanding pelayanan terakhir yang benar-benar diterapkan | Maksimal 20% per pelayanan |
| Ujung seluruh antrean terlihat | Boleh berkurang bertahap sampai batas minimum pengendali |

Contoh Timur: waktu dasar **150 detik** menjadi **120 detik** pada pelayanan pertama dengan sedikit deteksi dan pandangan sebagian. Pelayanan berikutnya boleh menjadi **112,5 detik**, lalu bertahan pada batas itu. Jika indikator kemacetan aktif, batasnya **150 detik**. Durasi tetap dibatasi maksimum pengendali.

Pada penandaan video, biarkan **“Ujung seluruh antrean terlihat di video”** tidak dicentang bila kendaraan berlanjut di luar gambar atau tertutup. Kalibrasi lama otomatis dianggap pandangan sebagian. Rasio batas/penurunan dapat disetel di `configs/adaptive-policy.json` melalui `video_baseline_floor_ratio` dan `video_maximum_drop_ratio`.

Nol deteksi pada pandangan sebagian juga tidak dianggap bukti jalan kosong. Pendekat itu tetap ikut pemerataan pelayanan dengan jumlah terdeteksi tetap nol; tidak ditambahkan kendaraan fiktif ke data atau peta. Pendekat dengan pandangan penuh yang terkonfirmasi kosong dapat dilewati saat pendekat lain membutuhkan pelayanan.

`ATCS_MAXIMUM_GREEN_SECONDS` bawaan 180 detik mengizinkan baseline 150 detik. Horizon rencana mencakup hijau dan cadangan transisi, paling lama 300 detik; timeout data dan heartbeat tetap bekerja terpisah. Sumber sintetis mempertahankan kebijakan lamanya. Pengukuran area kotak merupakan indikator gambar, bukan okupansi jalan fisik atau jumlah kendaraan tersembunyi. Batas konservatif ini perlu divalidasi pada video utama sebelum durasi dinyatakan optimal.

## Riwayat

Monitor menampilkan paling banyak **20 kejadian terakhir** sesuai filter, dengan tombol sembunyikan/tampilkan. Tautan **Riwayat lengkap** membuka `/history`, yang memerlukan login operator, memiliki filter, dan memuat 50 kejadian per halaman.

ATCS menyimpan setiap kejadian sejak startup baru ke **`work/history/events.sqlite3`**, lintas sesi dan restart. Lokasi dapat diatur dengan `SIGAP_EVENT_ARCHIVE`. Penghapusan baris dari jendela tampilan tidak menghapus arsip. Tidak ada penghapusan arsip otomatis. Kegagalan penyimpanan ditandai sebagai arsip tidak tersedia; pengendali tetap berjalan.

Jika layanan ATCS dijalankan dengan Docker Compose, arsip memakai volume persisten **`sigap_history`** di `/app/work/history`; volume tetap ada saat container diganti. Backup Docker perlu menyertakan volume ini. Konfigurasi Compose telah diperiksa tanpa menyalakan container.

Arsip baru mencatat sejak fitur ini diaktifkan. Kejadian lama yang sudah hilang dari memori sebelum pemasangan tidak dapat dipulihkan secara retroaktif. Backup data lokal perlu menyertakan folder `work/history`; file SQLite tidak diunggah ke GitHub.

## Validasi

Tes mencakup retensi/expiry, ID ambigu dan batas kamera, jumlah ikon sama dengan track stabil, polling putus/stale, retensi tanpa antrean palsu, durasi konservatif dan hijau panjang, fallback data basi, arsip lintas restart/paginasi, autentikasi arsip, 20 baris dan hide/show, serta kontrak/build frontend. Tes PostgreSQL nyata dan proses server/GPU tidak dijalankan selama layanan diminta berhenti. Validasi visual dengan empat video utama masih dilakukan saat aplikasi dinyalakan kembali.
