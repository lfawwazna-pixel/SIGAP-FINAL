# Kendaraan dan percobaan — Tahap 2E / 2F

Empat lengan simpang diperpanjang dari batas lama 18–782 menjadi -200–1000 pada koordinat skema. Pusat tetap (400,400). Sejak perbaikan 4 Oktober 2026, ruas pintas dan jalan utama menjadi satu permukaan bertepi kontinu; tetap satu lajur, cukup untuk mobil selebar 18 unit. Kurva dipanjangkan dari titik (470,100) ke (700,330) sebelum dirotasi per arah. Ukuran ini skematis, bukan meter atau hasil survei. Geometri sumber berada pada configs/map-geometry.json, dibaca backend dan disalin ke frontend oleh generator kontrak. Zoom tersedia 50–200% setiap 10%, default 100%, dan hanya mengubah tampilan.

## Tiga pilihan ruang kerja

| Pilihan | Sumber data | Kendali dan perilaku |
|---|---|---|
| ATCS | Kendaraan sintetis pada proses ATCS | Fixed-time utama, 1×, terus berjalan; tidak ada start/pause/reset/EVP lewat UI |
| SIGAP | Kelak CCTV dan YOLO | Panel kendali 3/4: kesiapan, heartbeat, tanda terima, tindakan dan riwayat; aktivasi utama tetap menunggu sumber CCTV |
| Simulasi | Kendaraan sintetis milik percobaan | Jam dan pengendali terpisah, fixed-time/adaptif sintetis, kontrol waktu, pengaturan arus dan uji EVP |

Memilih tampilan tidak mengirim perintah ke ATCS utama. ATCS tetap berjalan saat simulasi dijeda, dipercepat, direset, ditutup atau backend dimatikan. Kembali ke ATCS membaca keadaan terbaru dari proses yang sama. Proses ATCS sendiri tetap dapat berhenti karena host/proses gagal atau sengaja direstart untuk pembaruan; pergantian tampilan tidak melakukan restart tersebut.

## Pergerakan kendaraan

TrafficWorld memuat 16 lintasan: kiri lajur luar, lurus luar, lurus dalam dan kanan dalam untuk U/T/S/B. Lajur luar berbagi lintasan masuk sampai percabangan; ruas pintas kiri melewati pulau pemisah lalu bergabung ke lajur keluar luar. Lajur dalam berbagi lintasan lurus/kanan sebelum simpang. Setiap kendaraan memiliki ID, jenis, asal, gerakan, jarak lintasan, waktu tunggu dan status sudah dilayani.

Substep maksimum 50 ms dipakai pada runtime. Gerak dibatasi oleh sinyal, jarak antarkendaraan, ruang keluar dan kendaraan pada area konflik. Kendaraan baru tidak masuk pada kuning atau merah; kendaraan yang telah melewati gerbang pelayanan menyelesaikan lintasannya. Hanya satu pendekat bersinyal memperoleh hijau/kuning. Perhitungan posisi dan sinyal berada di server; browser menggambar snapshot, bukan menentukan fase.

Selubung jarak pusat 34 unit memuat panjang mobil 26 unit dan jarak antar kendaraan. Grid spasial membatasi pemeriksaan tetangga. Ruas pintas memberi jalan sebelum mencapai jalur keluar bersama; kendaraan yang sudah berada pada jalur keluar didahulukan. Pemeriksaan ini konservatif dan bukan model perilaku pengemudi lapangan.

Ruang keluar dibatasi paling banyak 12 kendaraan yang sudah berkomitmen menuju lajur keluar sama. Skenario keluaran terblokir menahan masuk ke tujuan tersebut. Kemunculan yang tidak memiliki ruang aman ditolak/digeser ke belakang, bukan bertumpuk. Maksimal 160 kendaraan hidup per dunia. Arus default 10 kendaraan/menit per pendekat; laju sintetis dan seed dapat diulang. Arus 0 menghentikan kemunculan otomatis pada pendekat tersebut. Kendaraan tidak pindah lajur atau menembus antrean.

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

Spawn ambulans/pemadam memilih asal U/T/S/B serta jarak 60/100/180/350 unit skema. Kendaraan darurat percobaan berjalan lurus pada lajur dalam. Jarak dihitung sepanjang lintasan menuju garis henti, bukan koordinat GPS atau meter. Beberapa EVP dapat disiapkan saat jeda lalu dijalankan bersama. Jika posisi terisi, kendaraan ditempatkan lebih ke belakang; panel peta memakai posisi aktual hasil penempatan.

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
