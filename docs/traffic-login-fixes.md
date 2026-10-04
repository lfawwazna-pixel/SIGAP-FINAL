# Perbaikan manuver dan login — 4 Oktober 2026

Laporan operator: dua mobil saling menunggu saat bertukar lajur, mobil berhenti menyerong di antrean, serta mobil berhenti jauh dari simpang. Implementasi sebelumnya hanya mengecek celah awal 55 unit, mengunci seluruh pendekat saat satu mobil berpindah, dan menahan mobil di batas persiapan sampai pemulihan 20 detik. Pemulihan tersebut tidak berlaku untuk mobil yang sudah menyerong.

## Perbaikan

Reservasi sekarang memerlukan koridor kosong sampai akhir perpindahan di kedua lajur. Urutan permintaan stabil; bantuan membuka celah tidak boleh membentuk siklus saling mengalah. Manuver yang berjauhan dapat berlangsung bersamaan. Kendaraan yang kehilangan kesempatan berbelok mengambil gerakan legal lajurnya sebelum percabangan, sambil tetap bergerak. Aturan ini hanya untuk dunia sintetis ATCS dan Simulasi; posisi CCTV nanti mengikuti tracking.

Aturan ini konservatif: pada antrean rapat, kendaraan dapat kehilangan tujuan belok semula. Tujuan alternatif dicatat di peristiwa simulasi. Lampu merah dan keluaran penuh tetap dapat menghasilkan antrean; perbaikan tidak menjanjikan jalan selalu kosong. Kecepatan naik bertahap setelah berhenti. `stop_reason` tersedia dalam snapshot API dan tooltip kendaraan.

Login memakai `JunctionRoad` yang juga digunakan monitor: outline jalan, tiga lajur masuk/keluar, pulau pemisah, marka, median dan ruas pintas berasal dari sumber geometri bersama. Sorotan tiga rute berputar saat U/T/S/B dipilih. Ilustrasi login tidak menampilkan status lampu atau kendaraan aktual.

Panel ilustrasi berwarna #E8EDF4 dengan teks #17324D/#526575, jalan #C3CEDC, dan aksen #245FA5 yang juga dipakai form login. Aset PNG logo sudah memiliki alpha transparan; yang dihapus adalah background putih CSS pembungkusnya. Aset asli tidak digambar ulang.

## Verifikasi

- Regresi `tests/test_traffic_gridlocks.py`: pertukaran sejajar di empat arah, antrean diam di lajur asal/tujuan, penyelesaian manuver ketika pemimpin berhenti, batas persiapan tanpa berhenti buatan, dua manuver berjauhan, dan alasan berhenti.
- Regresi perpindahan 36 kombinasi awal/tujuan/arah, dua perpindahan sebelum percabangan, antrean merah/ruas pintas, EVP dari belakang dan pengosongan arus acak tetap dijalankan.
- Tes UI membandingkan outline dan marka login dengan monitor, memeriksa pemilihan rute serta tooltip alasan berhenti. Tes autentikasi tetap mencakup sesi, CSRF dan login/logout.
- Browser Use menolak localhost karena preferensi izin tersimpan. Tidak ada pemeriksaan screenshot atau Ctrl +/- browser secara langsung; tes DOM, koordinat dan build bukan pengganti pemeriksaan visual tersebut.

Hasil pada proyek utama: 196 tes Python lulus, satu tes PostgreSQL khusus dilewati karena variabel database uji tidak tersedia; satu peringatan deprecation Starlette/httpx tetap muncul. Sebanyak 62 tes frontend, TypeScript, build produksi, sinkronisasi schema/geometri, dan `git diff --check` lulus. Setelah perapian kecil kode, 10 tes gridlock dijalankan kembali dan lulus.

Uji beban tambahan memakai fixed-time 85/150/95/100, kuning 3, semua merah minimum 2, seed 913, dan 24 kendaraan/menit/pendekat selama 900 detik; kemudian kedatangan dihentikan. Pada detik 300/600/900, jumlah selesai adalah 284/660/1013 dengan kendaraan aktif 128/121/134. Seluruh 1147 kendaraan yang diterima akhirnya keluar; 147 perpindahan dimulai dan durasi terlama 3,3 detik. Jarak diperiksa tiap dua detik simulasi; skenario regresi terarah memeriksanya setiap substep 0,05 detik. Ini validasi skenario terbatas, bukan bukti untuk semua kemungkinan arus.

Backend dan ATCS dimuat ulang dari proyek utama. Pemeriksaan HTTP melalui Vite lulus untuk login/logout, konfigurasi tiga lajur, snapshot `stop_reason`, spawn EVP dari belakang, reset eksperimen, dan run ATCS yang tetap sama selama spawn/reset. Eksperimen uji sudah dibersihkan melalui reset. Kontras teks utama/pelengkap pada panel ilustrasi adalah 11,16:1 / 5,13:1 dan tombol putih-biru 6,45:1, dihitung dari warna CSS.

Tahap 5, model YOLO dan perubahan prioritas EVP tidak termasuk perubahan ini.
