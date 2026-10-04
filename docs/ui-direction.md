# Arah UI/UX SIGAP

Acuan visual: [Oil and Gas Operator Dashboard](https://www.figma.com/community/file/1553501642495669298/oil-and-gas-operator-dashboard). Gunakan hierarki ruang kerja operator dan kepadatan informasinya sebagai arah desain. Implementasi 2C menggunakan komponen dan peta sendiri; bukan salinan aset Figma.

## Karakter

Nama arah: **Ruang Kendali Persimpangan**. Satu elemen utama: peta simpang yang langsung menjelaskan kondisi arus dan fase. Area lain lebih tenang dan mendukung keputusan operator.

Pada Tahap 2C, peta mendominasi kiri/tengah, panel operasional berada di kanan, riwayat berada di bawah. Informasi utama: siapa yang mengendalikan, fase aktif, kualitas data, dan alasan perubahan. Status koneksi dan mode terbaca melalui teks serta bentuk, tidak hanya warna.

## Peran warna dan tipografi

| Peran | Nilai |
|---|---|
| Latar abu dingin | `#EEF2F5` |
| Permukaan kerja | `#FFFFFF` |
| Teks utama | `#182B3A` |
| Teks sekunder | `#526575` |
| Aksen/fokus | `#1763A6` |
| Batas struktural | `#CCD6DF` |
| Indikator hijau | `#17804A` |
| Indikator merah | `#C53636` |
| Indikator kuning | `#B87500` |

IBM Plex Sans untuk judul dan isi, IBM Plex Mono untuk waktu/angka operasional. Font dilayani dari paket lokal. Jangan memakai Inter, Roboto, Arial, atau system-ui sebagai suara merek. Teks status kecil menggunakan variasi hijau/kuning yang lebih gelap agar terbaca pada putih.

Spasi dasar 4/8 piksel. Area kerja utama cukup radius 6–8 piksel; tidak perlu membungkus setiap angka atau label dengan kartu. Border digunakan untuk membagi informasi, bukan dekorasi editorial.

## Interaksi

- Setiap tombol melakukan tindakan nyata; tombol yang belum ada fiturnya tidak ditampilkan sebagai tindakan aktif.
- Data kosong, data basi, koneksi putus, loading, dan kesalahan adalah keadaan tersendiri.
- Fokus keyboard terlihat dan label/teks mendampingi warna status.
- Peta interaktif menjelaskan pendekat/arus saat dipilih; tidak ada gerakan dekoratif. Garis biru merupakan penunjuk rute, bukan izin bergerak.
- Perintah kendali pada tahap berikutnya harus membedakan permintaan operator dari konfirmasi pengendali.

Hindari gradien dekoratif, warna ungu generik, latar krem “premium”, efek kaca/blur, kartu identik berulang, kotak bertumpuk, angka langkah tanpa urutan nyata, slogan, hover membesar/memantul, dan animasi tanpa tujuan operasional.

Tahap 2C mengganti layar fondasi menjadi monitor simpang. Kesiapan layanan dipertahankan dalam bagian yang dapat dibuka di bawah riwayat. Navigasi mengarah ke bagian riwayat/layanan yang benar-benar tersedia. Tidak ada sidebar kosong, KPI kendaraan fiktif, akun tiruan, atau tombol kendali yang belum bekerja.

Peta dibangun dari satu geometri pendekat yang diputar 90 derajat untuk empat arah. Identitas/arus diperiksa terhadap konfigurasi API. Di bawah 900 px, panel berpindah ke bawah peta; di bawah 560 px, panel menjadi satu kolom dan peta memiliki lebar minimum agar garis tetap dapat dibaca dengan menggeser area peta. Fokus keyboard dan teks status tersedia. Tata letak browser belum diperiksa secara visual karena izin Browser Use tersimpan memblokir pratinjau lokal.

## Login dan identitas operator — Tahap 2D

Halaman `/login` membagi ruang antara ilustrasi simpang berlatar biru baja `#173D55` dan formulir di permukaan putih dingin. Ciri utamanya tetap persimpangan: tombol U/T/S/B menyorot gerakan pendekat dan menjelaskan nama jalan serta tujuan belok kiri. Ilustrasi ditandai sebagai ilustrasi, tanpa angka kepadatan atau lampu aktual sebelum sesi terverifikasi.

Formulir mengutamakan label permanen, jarak klik yang cukup, autocomplete, paste, tampil/sembunyikan password, petunjuk Caps Lock, dan kesalahan yang dapat dibaca pembaca layar serta memperoleh fokus. Gerak jalur dan indikator proses hanya aktif saat pemeriksaan akses; preferensi reduced motion dihormati. Di bawah 760 px, susunan menjadi vertikal, ilustrasi dipadatkan, dan pemilih pendekat disembunyikan agar formulir tetap menjadi fokus.

Setelah verifikasi, `/monitor` menampilkan nama operator di kanan atas. Menu operator memuat peran pemantauan, nama pengguna, batas sesi, serta tindakan keluar yang benar-benar mencabut sesi server. Tidak ada profil tiruan, pendaftaran publik atau tautan lupa password tanpa fungsi. Sesi gagal dipulihkan mendapat layar penjelasan dan tombol coba lagi; monitor tidak dibuka hanya berdasarkan perubahan alamat halaman.

Interaksi, transisi sesi dan navigasi telah diuji dengan jsdom. Ukuran, kontras hasil rendering, fokus visual dan tata letak responsif masih memerlukan pemeriksaan browser ketika pembatasan izin tersedia untuk diubah oleh pengguna.

## Kendaraan dan ruang percobaan — 2E/2F

Navigasi utama menyediakan ATCS, SIGAP dan Simulasi. Pilihan SIGAP menjelaskan bahwa CCTV/YOLO belum terhubung. Simulasi memuat kontrol eksperimen yang benar-benar bekerja pada mesin terpisah, sementara strip status menunjukkan ATCS utama terus berjalan. Tidak ada pause/reset/percepatan untuk ATCS utama.

Empat lengan peta diperpanjang; ruas pintas kiri diperlebar untuk satu mobil; rambu lajur dipindahkan ke sisi jalan. Kendaraan biasa biru baja, ambulans putih dengan tanda silang, pemadam merah dengan pola tangga. Ikon dan label ID membantu membedakan EVP selain warna. Zoom dan area geser menjaga seluruh jalan dapat diperiksa. Gerak SVG hanya mengikuti snapshot kendaraan dari server; preferensi reduced motion menghilangkan interpolasi posisi.

Panel percobaan menyediakan sumber strategi, keputusan/target EVP, jumlah kendaraan, antrean, statistik tunggu, kontrol arus dan riwayat. Jarak kemunculan ditulis dalam unit skema. Tidak ada klaim posisi kendaraan CCTV atau meter lapangan. Rincian: [Panduan percobaan](traffic-simulation.md).
