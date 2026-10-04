# Monitor persimpangan — Tahap 2C

Monitor bersifat baca saja. ATCS tetap menjalankan siklusnya ketika monitor ditutup atau backend terputus. Sejak Tahap 2D, akses monitor memerlukan login dan sesi operator valid; lihat [akses operator](operator-auth.md). Kendaraan sintetis dan ruang percobaan ditambahkan pada 2E/2F. Pengiriman override operasional belum dibuat; lihat [kendaraan dan percobaan](traffic-simulation.md).

## Geometri dan cara menggunakan

- U/S memakai Jl. Ibrahim Adjie; T/B memakai Jl. Soekarno Hatta sesuai konfigurasi. Setiap pendekat mempunyai dua lajur masuk dan dua lajur keluar, dengan lalu lintas di kiri.
- Lajur luar bercabang sebelum garis henti. Cabang kiri melewati ruas pintas di sisi luar pulau pemisah, bergabung kembali setelah simpang, dan dilengkapi rambu beri jalan. Cabang lurus mengikuti lampu.
- Lajur dalam untuk lurus/kanan. Tidak digambar putar balik atau perpindahan lajur di tengah simpang. Rambu arah tiap lajur dan panah marka menunjukkan pergerakan yang diperbolehkan dalam model.
- Klik label arah pada peta, atau tombol U/T/S/B di panel. Keyboard Enter/Spasi memilih label peta. Panel menjelaskan asal, tujuan, dan sinyal pendekat yang dipilih.
- Tombol Rute terpilih mengatur garis putus-putus lurus/kanan. Garis biru pada ruas pintas tetap terlihat; warna rute tidak menunjukkan izin melintas. Lampu dan label merah/kuning/hijau adalah indikator status sinyal.
- Geometri simetris dan rambu merupakan skema simulasi, bukan hasil pengukuran atau inventaris rambu lapangan.

Panel kanan menampilkan pengendali, mode, fase, pendekat aktif, sisa waktu, baseline U/T/S/B, dan keadaan area konflik. Default sumber konflik kini mengikuti kendaraan sintetis pada proses ATCS dan ditampilkan **Kosong/Terisi**. Ini bukan pengamatan CCTV. Saat semua merah diperpanjang, countdown menjadi **—** disertai alasan penahanan; tidak menampilkan hitung mundur fiktif.

## Data, koneksi, dan waktu

Semua permintaan browser memakai backend `/api`, bukan akses langsung ke ATCS. Feed kendaraan 2E/2F dibaca setiap 250 ms; lampu, countdown dan kendaraan memakai satu snapshot feed ketika sumbernya tersedia dan ID sesi cocok. Semua respons divalidasi terhadap JSON Schema hasil generasi. Pemeriksaan relasi antarkolom dilakukan lagi sebelum menyalakan sinyal pada peta.

| Pembacaan | Interval setelah respons | Timeout |
|---|---|---|
| Status ATCS | 500 ms | 1.800 ms |
| Riwayat ATCS | 2.000 ms; segera jika masih ada halaman | 2.500 ms |
| Konfigurasi/kesiapan | 10.000 ms | 5.500 ms per permintaan |

Pembacaan status, riwayat dan health menggunakan loop terpisah. Sejak Tahap 2D, setiap permintaan monitor tetap memeriksa sesi database; kegagalan database dapat memblokir akses, meskipun mesin ATCS terus berjalan. Masing-masing loop tidak membuat permintaan tumpang tindih. Tombol periksa ulang membatalkan pembacaan lama dan membaca ulang, tanpa mereset sesi ATCS.

`Math.ceil(remaining_seconds)` hanya membulatkan nilai ATCS untuk tampilan. Browser tidak mengurangi angka berdasarkan waktunya sendiri atau menentukan fase berikutnya. Timer browser dipakai untuk polling/kedaluwarsa data saja.

Status tersedia hanya jika identitas simpang, seluruh sinyal, fase, clearance, dan countdown konsisten. Umur `observed_at - updated_at` dari server ditambah waktu perjalanan request harus tidak melebihi 2 detik. Urutan snapshot/waktu simulasi yang mundur pada sesi sama ditolak; nomor snapshot yang tidak maju selama 2 detik ditandai basi. Pengawas tambahan membuang status jika tidak ada pembaruan valid selama 2,5 detik. Pemeriksaan umur menggunakan pasangan waktu dari server dan jam monotonic browser, bukan membandingkan jam kalender dua komputer.

Koneksi gagal, kontrak salah, status tidak operasional, atau data basi membuat lampu abu-abu dengan tanda **?** dan countdown **—**. Ini berarti keadaan belum diketahui, bukan klaim lampu telah berubah merah. Ketika tab tersembunyi, pemantauan lampu dijeda dan tampilan aktif dibatalkan; saat tab kembali, respons baru wajib diterima. Pemutusan jaringan dan balasan dari permintaan yang sudah dibatalkan tidak mempertahankan lampu hijau lama.

Jika konfigurasi belum tersedia/tidak cocok dengan geometri, peta tidak digambar sebagai data terverifikasi. Jika pemeriksaan konfigurasi berikutnya gagal, monitor menunggu konfigurasi valid lagi. Respons health 503 yang valid tetap dapat menunjukkan API hidup; itu terpisah dari kelayakan status lampu. Kegagalan autentikasi database dapat menghasilkan 503 sebelum laporan health dibaca; liveness publik hanya menyatakan proses API menjawab. Respons sesi 401/403 menutup monitor dan mengembalikan pengguna ke login.

## Riwayat

Riwayat dibaca memakai `run_id` terverifikasi dari status serta cursor `next_after`. Halaman maksimal 500 item dibaca berurutan. Tampilan menyimpan maksimal 100 kejadian terbaru, enam baris pada awalnya, dengan tombol untuk membuka semuanya dan filter pergantian fase/gangguan. Timestamp memakai WIB.

ID simpang, ID sesi, identitas event, urutan, dan cursor diperiksa sebelum penggabungan. Halaman dari sesi berbeda ditolak sampai status mengonfirmasi sesi baru; pergantian sesi membuang riwayat tampilan sebelumnya dan mulai dari cursor nol. Riwayat yang terpotong ditandai. Gangguan pembacaan menandai baris lama sebagai riwayat tersimpan, bukan pembaruan berhasil. Tidak ada baris contoh, peristiwa buatan, atau penyimpanan permanen baru.

## Batas verifikasi

Pengujian komponen memakai jsdom: menguji label, event keyboard/klik, perubahan data, dan lifecycle polling; tidak menguji tata letak piksel. Sambungan HTTP lokal melalui Vite/backend/ATCS sudah diperiksa. Pengujian visual browser belum dilakukan: setelah izin eksplisit pengguna, Browser Use tetap menolak localhost karena pengaturan izin tersimpan. Tidak digunakan jalur browser alternatif.

Pemeriksaan manual yang masih diperlukan: tampilan desktop/tablet/ponsel, keterbacaan marka dan posisi rambu, fokus keyboard pada peta, serta pergeseran peta/tabel pada layar kecil. Ini tidak menghalangi pengujian logika, tetapi belum membuktikan kualitas rendering di browser.
