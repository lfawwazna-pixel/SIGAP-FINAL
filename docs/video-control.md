# Video utama dan kendali SIGAP

Rekaman MP4 per U/T/S/B disimpan bersama metadata dalam `work/media`, langsung diputar ketika backend dimulai, dan terus looping. Upload lewat panel CCTV langsung mengganti sumber aktif/default pendekat tersebut. Batas 256 MB per file; video dibaca secara bertahap sehingga durasi tujuh menit tidak dimuat seluruhnya ke RAM. Pemrosesan dan pratinjau dibatasi 5 FPS agar empat sumber tetap ringan. Sesi kamera tetap saat looping; generasi ByteTrack, ID peta, antrean, dan waktu tunggu direset pada setiap putaran.

ATCS dan SIGAP menggunakan satu decoder/server. Ketika hasil tracking mutakhir, ATCS mengambil JPEG asli dari pekerjaan tracking itu; SIGAP mengambil JPEG ber-overlay dengan nomor frame, sesi, dan waktu media sama. Navigasi tidak memutar ulang atau menghentikan decoder. Inferensi yang terlambat, berasal dari sumber/generasi lama, atau gagal tidak dipakai. Video asli dapat terus ditampilkan saat tracking bermasalah.

Kamera langsung yang putus dicoba dihubungkan kembali setelah decoder berhenti, tanpa menghapus kalibrasi. Proses reconnect mereset tracker. Selama data tidak mutakhir, ATCS tetap melakukan fallback; pemulihan otomatis SIGAP baru berlaku setelah semua pendekat kembali sehat.

## Kalibrasi dan pengukuran

Pilih pendekat, klik **Tandai lajur & garis henti**, lalu tandai tiga poligon lajur masuk sebelum garis henti. Lajur kiri/outer untuk ruas pintas; tengah/middle untuk lurus; kanan/inner untuk belok kanan. Jangan menumpangtindihkan lajur. Garis henti memakai dua titik. Simpan penandaan untuk setiap kamera. Unggahan baru menghapus penandaan lama. Titik bawah-tengah bounding box menentukan lajur; kendaraan di luar ROI atau sudah melewati garis henti dikeluarkan dari kebutuhan lampu.

Kendaraan terkontrol berasal dari lajur tengah/kanan; ruas pintas tidak menambah durasi hijau. Kendaraan dianggap diam setelah setidaknya 0,8 detik dengan perpindahan paling banyak 0,015 ukuran gambar per detik selama jendela 1,5 detik. Waktu tunggu dihitung dari pengamatan diam, bukan sejak kendaraan masuk video. Sampel/frame yang sama tidak memperpanjang waktu tunggu atau memperbarui waktu observasi. Kendaraan yang tertutup dapat kehilangan ID. Estimasi ini memerlukan perbandingan pengamatan manual; belum merupakan pengukuran kecepatan/jarak dalam meter. Keluaran diasumsikan terbuka karena belum ada ROI keluaran.

Peta memakai jumlah, lajur, posisi relatif ke garis henti, dan status diam dari tracking. Posisi diproyeksikan tanpa skala ke ruas masuk; gerakan sesudah garis henti tidak dibuat-buat. Video rekaman tidak berubah karena lampu simulasi; peta memvisualisasikan pengamatan dan menampilkan fase pengendali yang sama pada ATCS/SIGAP. Kelas ambulans/pemadam dapat digambar, tetapi deteksinya belum mengaktifkan prioritas EVP.

## Pengambilalihan dan fallback

Dengan `SIGAP_YOLO_ENABLED=true` dan `SIGAP_ADAPTIVE_VIDEO=true` (default), pengirim adaptif membaca video, bukan `/measurements` sintetis. Semua empat pendekat wajib memiliki video/hasil tracking mutakhir serta kalibrasi. Tidak ada deteksi bukan otomatis gangguan: nol kendaraan pada ROI yang valid adalah pengamatan sah. Kunci komunikasi antarlayanan wajib tersedia.

Aktivasi pertama dilakukan lewat **Aktifkan kendali SIGAP**. ATCS tetap menerapkan fase dan membatasi hijau, kuning, semua merah, serta clearance konflik. Indikator di kedua tampilan menunjukkan pengendali aktual. Fase/durasi dan data kendaraan video ditampilkan bersama ketika SIGAP memiliki kendali.

Ketika salah satu pendekat tidak layak, sumber berhenti, heartbeat hilang, atau rencana tidak tersedia, ATCS mencabut sesi SIGAP dan kembali ke fixed-time melalui transisi aman. Sesudah aktivasi, backend dapat meminta pengambilalihan kembali ketika empat sumber pulih; permintaan tetap melewati arbiter ATCS. **Kembalikan ke ATCS** membatalkan pemulihan otomatis. Tombol **Batalkan pemulihan otomatis** juga tersedia selama gangguan/fallback dan dapat meminta pelepasan sesi yang masih aktif. Restart backend memerlukan aktivasi pertama lagi. Pada batas looping, hanya pengamatan lama yang masih dalam batas kesegaran asli boleh menjembatani waktu pemanasan singkat; timestamp tidak diperbarui.

ATCS lokal tetap prototipe: deteksi area konflik masih berasal dari dunia sintetis, bukan CCTV lapangan. Kalibrasi empat video utama, validasi antrean/tunggu manual, dan uji klip EVP perlu dilakukan sebelum klaim akurasi atau penggunaan lapangan. Mengganti video tidak membutuhkan training ulang; evaluasi deteksi pada video baru menentukan apakah model perlu ditingkatkan.

## Menjalankan versi lokal dengan vision

Setelah model, runtime vision, `.env`, PostgreSQL, dan build frontend tersedia, jalankan dari folder proyek:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-sigap.ps1
```

Skrip menjalankan ATCS khusus di 18001, backend di 18000, dan frontend di 15173 agar tidak bersaing dengan pengirim sintetis versi lama di 8000/8001. Konfigurasi vision hanya diterapkan pada proses yang dijalankan; `.env` tidak ditimpa. Log dan identitas proses disimpan dalam `work/runtime`. Jangan menjalankan dua launcher pada port yang sama.
