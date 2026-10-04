# Kendaraan dan percobaan — Tahap 2E / 2F

Revisi tiga lajur sebelum Tahap 5 memakai batas -400–1200 pada koordinat skema, dengan pusat (400,400). Tiap pendekat mempunyai tiga lajur masuk dan keluar. Ruas pintas kiri tetap satu lajur mobil, dengan permukaan jalan kontinu dan pulau pemisah. Kurva acuan bergerak dari (510,100) ke (700,290), dirotasi untuk empat arah. Ukuran ini skematis, bukan meter atau hasil survei. configs/map-geometry.json menjadi sumber geometri backend dan frontend. Zoom 50–200% setiap 10%, default 100%, hanya mengubah tampilan.

## Tiga pilihan ruang kerja

| Pilihan | Sumber data | Kendali dan perilaku |
|---|---|---|
| ATCS | Kendaraan sintetis pada proses ATCS | Fixed-time utama, 1×, terus berjalan; tidak ada start/pause/reset/EVP lewat UI |
| SIGAP | Kelak CCTV dan YOLO | Panel kendali 3/4: kesiapan, heartbeat, tanda terima, tindakan dan riwayat; aktivasi utama tetap menunggu sumber CCTV |
| Simulasi | Kendaraan sintetis milik percobaan | Jam dan pengendali terpisah, fixed-time/adaptif sintetis, kontrol waktu, pengaturan arus dan uji EVP |

Memilih tampilan tidak mengirim perintah ke ATCS utama. ATCS tetap berjalan saat simulasi dijeda, dipercepat, direset, ditutup atau backend dimatikan. Kembali ke ATCS membaca keadaan terbaru dari proses yang sama. Proses ATCS sendiri tetap dapat berhenti karena host/proses gagal atau sengaja direstart untuk pembaruan; pergantian tampilan tidak melakukan restart tersebut.

## Pergerakan kendaraan

TrafficWorld memuat 12 lintasan akhir: kiri/luar, lurus/tengah dan kanan/dalam untuk U/T/S/B. Mobil biasa memilih tujuan, lajur awal, kecepatan 44–52 unit/detik dan jeda kedatangan secara acak dengan seed yang dapat diulang. Lajur awal tidak mengunci tujuan. Perpindahan memakai satu lajur per manuver sepanjang 125 unit, dengan gerak lateral halus; perpindahan dua lajur dilakukan dua kali, dipisahkan 24 unit perjalanan.

Zona persiapan U berada dari y=-330 sampai y=40, lalu dirotasi per arah. Percabangan kiri mulai y=100 dan garis henti y=257. Jarak depan minimal 55 unit dan belakang 50 unit diperiksa sebelum pindah; kendaraan menempati kedua lajur selama manuver. Pengendara pada lajur tujuan dapat menunggu untuk membuka celah. Manuver yang berdekatan diserialkan pada setiap pendekat. Jika celah tetap tertutup selama 20 detik, mobil mengikuti gerakan sah dari lajur saat ini; keputusan dibuat di hulu, dicatat, dan tidak mengubah posisi mobil secara mendadak. EVP masuk pada lajur tengah sehingga tujuan lurus dan aturan prioritasnya tetap konsisten.

Substep maksimum 50 ms dipakai pada runtime. Gerak dibatasi oleh sinyal, jarak antarkendaraan, ruang keluar dan kendaraan pada area konflik. Kendaraan baru tidak masuk pada kuning atau merah; kendaraan yang telah melewati gerbang pelayanan menyelesaikan lintasannya. Hanya satu pendekat bersinyal memperoleh hijau/kuning. Perhitungan posisi dan sinyal berada di server; browser menggambar snapshot, bukan menentukan fase.

Selubung jarak pusat 34 unit memuat mobil 26×18 unit dan jarak aman. Pemeriksaan menyapu segmen perpindahan tiap substep, termasuk gerak lateral, dengan grid spasial untuk tetangga. Tiga gerakan mengisi tiga lajur keluar berbeda; ruas pintas tidak menunggu arus di lajur sebelah, tetapi tetap berhenti jika lajur keluarnya penuh/terblokir. Pemeriksaan ini konservatif dan bukan model pengemudi lapangan.

Ruang keluar dibatasi paling banyak 16 kendaraan yang sudah berkomitmen menuju lajur keluar sama. Skenario keluaran terblokir menahan masuk ke tujuan tersebut. Semua kemunculan publik berada di batas belakang jalan; jika penuh, permintaan ditolak tanpa memindahkan kendaraan ke tengah peta. Maksimal 160 kendaraan hidup per dunia. Arus default 10 kendaraan/menit per pendekat; arus 0 menghentikan kemunculan otomatis.

ATCS memakai TrafficWorld lokal sebagai ConflictProvider. Area konflik kini berdasarkan kendaraan sintetis, bukan assumed_clear. Semua merah minimum diperpanjang sampai kendaraan bersinyal yang sudah masuk selesai melintas. Penyedia konflik khusus masih dapat dipasang untuk pengujian/integrasi berikutnya.

## Percobaan terpisah

Eksperimen berada pada proses backend, dimiliki akun operator dan disimpan dalam memori. Satu akun memiliki satu percobaan bersama semua tabnya. Maksimal empat akun memiliki ruang aktif; ruang dihapus setelah satu jam tanpa permintaan. Restart backend menghapus eksperimen, tetapi tidak mengubah proses ATCS utama. Jalankan satu worker backend untuk percobaan ini; penyimpanan lintas worker belum tersedia.

- Kondisi awal dijeda, strategi adaptif sintetis, kecepatan 1×.
- Mulai/jeda mengubah jam dan kendaraan eksperimen saja.
- Kecepatan 1×/2×/3× mempercepat seluruh waktu eksperimen (kendaraan, lampu dan riwayat) dengan substep tetap kecil.
- Reset meminta konfirmasi, membuat ID percobaan baru, menghapus kendaraan/statistik/riwayat, dan kembali dijeda. Arus, strategi, kecepatan serta pengaturan keluaran dipertahankan.
- Perubahan strategi berlaku pada pemilihan fase selanjutnya; tidak langsung melompati kuning/semua merah atau memotong EVP.
- Pilihan arus U/T/S/B menerima 0–60 kendaraan/menit. Form menampilkan laju yang telah diterapkan server.
- Keluaran terblokir U/T/S/B atau semua terbuka memungkinkan pengujian antrean dan penahanan pelayanan.
- Zoom tidak mengubah geometri atau waktu. Layar kecil menyediakan area peta yang bisa digeser.

Jam berjalan pada task backend, bukan saat GET diterima. Jeda tab browser menghentikan pemantauan tampilan; eksperimen yang berjalan tetap maju di backend. Langkah catch-up dibatasi 0,5 detik waktu host setiap iterasi untuk mencegah lompatan posisi sesudah proses tersendat. Kecepatan adalah target waktu eksperimen, bukan jaminan kinerja pada host kelebihan beban.

## Adaptif sintetis dan EVP

Adaptif percobaan menilai pendekat yang memiliki kendaraan masuk berdasarkan umur sejak pelayanan ditambah empat kali jumlah kendaraan antre/masuk pada pendekat. Umur pelayanan mencegah pendekat sepi terus dikalahkan pendekat ramai. Hijau dipilih antara 10–40 detik menggunakan 8 + 3 × jumlah kendaraan. Ini heuristik percobaan yang berjalan nyata pada data sintetis, bukan hasil YOLO, evaluasi optimasi atau kendali adaptif operasional.

Spawn ambulans/pemadam memilih asal U/T/S/B dan selalu masuk dari ujung belakang pada lajur tengah, 657 unit skema dari garis henti. API tidak menerima jarak penempatan di tengah jalan. Untuk membuat dua EVP dengan jarak berbeda, jalankan percobaan dan tambahkan kendaraan berikutnya setelah yang pertama bergerak. Beberapa arah tetap dapat disiapkan bersamaan saat jeda; permintaan pada ujung masuk yang penuh ditolak. Prioritas menggunakan jarak aktual sepanjang lintasan, bukan GPS atau meter.

Aturan eksperimen yang diminta pengguna:

1. Ambulans mendahului pemadam pada antrean yang belum mendapat pelayanan.
2. Sesama jenis: kendaraan paling dekat garis henti didahulukan.
3. Jika jarak sama: waktu kemunculan, lalu ID menentukan urutan yang konsisten.
4. Saat EVP hadir, keputusan adaptif ditangguhkan. Kuning dan semua merah tetap dipenuhi sebelum pelayanan yang baru.
5. Pemilihan target dilakukan setelah clearance aman. Target dikunci sesudah hijau diberikan; EVP baru tidak memotong kendaraan yang sedang dilayani.
6. Selesai berarti ekor kendaraan melewati batas area konflik. Jika ada EVP lain, layani berikutnya melalui transisi aman.
7. Setelah semua EVP selesai, kembali ke strategi sebelumnya. Adaptif kembali adaptif; percobaan fixed-time kembali fixed-time.

Selama pelayanan darurat, countdown memakai keterangan “Sampai EVP selesai”, bukan angka fiktif. Jika jalan keluar terblokir, EVP tetap menunggu. Membuka kembali keluaran melalui kontrol percobaan memungkinkan pelayanan selesai. Ini aturan prioritas untuk eksperimen proyek; belum merupakan integrasi kendaraan darurat di lapangan.

## API dan kejujuran tampilan

| Endpoint | Akses | Kegunaan |
|---|---|---|
| ATCS GET /traffic | Diagnostik internal localhost | Snapshot kendaraan/sinyal dari runtime utama |
| Backend GET /api/atcs/traffic | Sesi operator | Proxy tervalidasi untuk kendaraan sintetis ATCS |
| Backend GET /api/simulation | Sesi operator | Ruang percobaan akun; pembacaan pertama menyiapkan ruang dijeda |
| Backend POST /api/simulation/commands | Sesi, origin/header aplikasi, CSRF | start, pause, reset, configure, spawn pada ruang akun itu sendiri |

Perintah membawa expected_run_id. Perintah untuk percobaan yang sudah direset ditolak 409 agar tab lama tidak mengubah percobaan baru. Bentuk input, arah, jenis, kecepatan dan batas arus divalidasi; field asing ditolak. Endpoint eksperimen tidak menerima URL, ID pemilik lain, atau perintah bagi pengendali utama. Akun operator dapat mengubah ruang eksperimennya; izin itu tidak memberi kendali ATCS/SIGAP operasional.

TrafficView memiliki sumber, ID simpang/percobaan, waktu, urutan snapshot, sinyal, kendaraan, antrean, statistik, kandidat EVP, target pelayanan dan riwayat. Kontrak dihasilkan dari contracts/traffic.py menjadi JSON Schema dan TypeScript. Frontend memeriksa schema, identitas, sumber, sinyal serta urutan snapshot. Polling 250 ms setelah balasan, timeout 1.800 ms, kedaluwarsa tampilan 2.500 ms. Permintaan lama/terputus tidak mempertahankan posisi aktif. Snapshot yang dijeda boleh memiliki nomor urut tetap.

Statistik menampilkan kendaraan di peta, jumlah selesai melintas, antrean U/T/S/B, serta rata-rata tunggu kendaraan yang sudah selesai. Belum ada statistik CCTV atau klaim tundaan lapangan. Riwayat percobaan menampung 100 kejadian terakhir dan terpisah dari riwayat ATCS utama.

Protokol override/heartbeat/fallback terhadap ATCS tiruan kini tersedia pada [Tahap 3/4](control-integration.md), diuji dengan proses pengirim terpisah. Ruang 2F tetap terisolasi dan tidak mengendalikan ATCS utama. Pipeline CCTV/YOLO dan EVP dari deteksi lapangan belum tersedia; panel SIGAP menampilkan kesiapan yang sebenarnya.
