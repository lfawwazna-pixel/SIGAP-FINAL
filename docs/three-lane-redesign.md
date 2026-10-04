# Redesain tiga lajur sebelum Tahap 5

Permintaan: tiga lajur per pendekat, perpindahan satu/dua lajur sebelum simpang, ruas pintas kiri yang melewati antrean lampu, dan kendaraan darurat masuk dari belakang jalan. Tahap 5 tidak ditambahkan dalam perubahan ini.

Perbaikan lanjutan untuk laporan kendaraan saling mengunci dan pembaruan login dicatat dalam [perbaikan manuver dan login](traffic-login-fixes.md). Bagian verifikasi awal di bawah menyimpan hasil sebelum perbaikan lanjutan tersebut.

## Geometri dan perilaku

- Pusat skema (400,400), batas jalan -400–1200. Setiap arah memiliki tiga lajur masuk dan keluar; median, empat pulau, garis henti, rambu, panah dan kurva diperbarui bersama.
- Di akhir pendekat, kiri menuju ruas pintas; tengah lurus; kanan belok kanan. Tujuan dan lajur awal mobil sintetis dipilih terpisah sehingga seluruh kombinasi awal/tujuan dimungkinkan.
- Zona pindah lajur U: y=-330 sampai y=40. Percabangan kiri y=100, garis henti y=257. Arah lain memakai rotasi yang sama.
- Setiap manuver berpindah satu lajur sepanjang 125 unit dengan kurva lateral halus. Dua perpindahan dipisahkan perjalanan 24 unit. Gerak longitudinal dan lateral memakai koordinat SVG yang sama.
- Sebelum melipir, koridor depan pada lajur asal dan tujuan harus kosong sepanjang 165 unit (125 manuver + 34 jarak pusat aman + 6 margin). Celah belakang lajur tujuan minimal 50 unit. Kedua lajur tetap ditempati selama manuver. Reservasi yang berjauhan boleh berjalan bersamaan; reservasi yang berpotongan harus menunggu.
- Permintaan menyimpan waktu awal dan ID sebagai prioritas stabil. Kendaraan belakang boleh memperlambat untuk membuka celah hanya jika koridor depan tersedia. Pemberi jalan tidak meminta kendaraan prioritas untuk mengalah kembali.
- Jika kesempatan pindah lajur terlewat pada batas keputusan, mobil mengikuti gerakan sah lajurnya tanpa berhenti selama 20 detik. Keputusan dicatat sebelum percabangan, tanpa loncatan posisi. Antrean karena lampu atau keluaran penuh tetap dimungkinkan.
- Kendaraan berakselerasi dari diam dan memperlambat saat mendekati pengikut antrean di zona perpindahan. Snapshot menyertakan `stop_reason`, yang ditampilkan pada tooltip mobil untuk membedakan lampu, antrean, keluaran penuh, konflik, penjagaan jarak, dan kendaraan diam.
- Selubung pusat 34 unit dan pemeriksaan segmen gerak mencegah tumpang tindih badan mobil 26×18 unit. Gerakan di ruas pintas/tengah simpang tidak melakukan pindah lajur.
- ATCS dan Simulasi menggunakan TrafficWorld yang sama. Tujuan, lajur awal, kecepatan dan jeda kedatangan bervariasi; seed mempertahankan kemampuan mengulang percobaan. Mode SIGAP belum memiliki sumber CCTV/YOLO.

## EVP

Ambulans/pemadam selalu masuk pada lajur tengah di ujung belakang pendekat terpilih, 657 unit dari garis henti. UI tidak menyediakan penempatan dekat lampu dan API menolak field `distance`. Jika pintu masuk penuh, spawn ditolak sampai ada ruang. Perbedaan jarak antarkendaraan dibuat dengan selang waktu kemunculan.

Prioritas jenis ambulans/pemadam, jarak aktual, penguncian target yang sedang dilayani, transisi kuning/semua merah, dan pemulihan strategi tetap diuji. Helper internal tes dapat membuat fixture pada jarak tertentu; kemampuan tersebut tidak diekspos ke endpoint.

## Kontrak dan penerapan

IntersectionConfig versi 2.0 menyatakan tiga lajur dan pemetaan `outer.left`, `middle.straight`, `inner.right`. Snapshot kendaraan menambahkan `lane`, `target_lane`, `changing_to`, `stop_reason`, serta rentang koordinat baru. Schema Python, salinan JSON frontend dan TypeScript telah digenerasi bersama. Format kendali Tahap 3/4 dan skema database tidak diubah.

Terapkan seluruh perubahan sekaligus, lalu restart backend dan ATCS agar geometri/kontrak baru dimuat. Vite yang sedang berjalan membaca perubahan frontend melalui reload. Restart layanan memperbarui sesi ATCS dan menghapus eksperimen dalam memori; akun/database tetap tersedia. Perpindahan mode pada UI tidak melakukan restart tersebut.

## Verifikasi

Diuji pada salinan kerja `work/sigap-three-lanes` dari proyek pada commit `cf8fdad`, 4 Oktober 2026:

- 187 tes Python lulus, termasuk PostgreSQL nyata, independensi proses ATCS, protokol override/fallback dan 56 kasus redesain lajur. Satu peringatan deprecation Starlette/httpx yang sudah ada tetap muncul.
- 60 tes frontend lulus; pemeriksaan TypeScript, sinkronisasi kontrak/geometri dan build produksi lulus.
- Pada lingkungan sandbox Windows, esbuild bundler konfigurasi tidak bisa menelusuri salah satu direktori induk. Verifikasi memakai Node 26 dan opsi `--configLoader native` untuk Vite/Vitest; konfigurasi produk tidak diubah untuk keterbatasan lingkungan tersebut.
- Semua 36 kombinasi arah, lajur awal dan tujuan diuji untuk perpindahan bersebelahan, kelancaran posisi, dan penyelesaian sebelum percabangan. Tes tambahan meliputi celah tertutup, manuver berlawanan, penyelesaian dua perpindahan pada batas zona, pilihan rute saat celah terlewat, antrean merah yang dilalui ruas pintas, serta spawn EVP pada empat arah.
- Arus acak dengan seed 7, 42 dan 913, 18 kendaraan/menit per arah selama 180 detik lalu dikosongkan, lolos variasi perpindahan, jarak aman dan antrean habis.
- Uji fixed-time memakai baseline 85/150/95/100, kuning 3, semua merah minimum 2, seed 42, arus 18 per arah, substep 0,1 detik. Pada detik 150/300/450/600/750/900/1050/1200/1350, jumlah selesai adalah 76/177/302/443/560/665/814/929/1028. Setelah kemunculan dihentikan pada detik 1350, semua 1178 kendaraan yang diterima sudah keluar pada detik 1800. Pemeriksaan jarak tiap dua detik lolos; regresi manuver dan antrean juga memeriksa tiap substep.
- Inspeksi visual browser belum dilakukan. Peluncuran pratinjau terpisah ditolak oleh kebijakan izin sesi. Hasil jsdom dan pengujian koordinat tidak menggantikan pemeriksaan piksel/browser.

Tidak ada model YOLO, pipeline video, algoritma operasional Tahap 5 atau perubahan prioritas EVP baru yang ditambahkan. Integrasi posisi CCTV nanti memerlukan tracking dan pemetaan koordinat; kendaraan sintetis tidak diklaim sebagai hasil deteksi.

### Penerapan pada proyek utama

Pada 4 Oktober 2026, patch terkonfirmasi terpasang di `C:\Users\Muhammad Luthfi Fawwazna\Project\PROJECT-SIGAP-ASTRA` melalui pemeriksaan balik `git apply --reverse --check`. Backend dan ATCS dimuat ulang dari direktori tersebut.

Pemeriksaan HTTP melalui Vite di `http://127.0.0.1:5173` lulus: login/logout, konfigurasi versi 2.0 dengan tiga lajur masuk/keluar, lalu lintas ATCS aktif dengan atribut lajur, dan geometri frontend terbaru. Spawn ambulans U pada eksperimen jeda menghasilkan posisi (470,-400), lajur tengah, 657 unit sebelum garis henti; parameter jarak lama ditolak (422). Spawn dan reset eksperimen tidak mengubah run ATCS. Eksperimen uji sudah direset. Pemeriksaan ini belum mencakup inspeksi visual browser.
