# Video YOLO26s dan ByteTrack

SIGAP menampilkan hasil model enam kelas `car`, `motorcycle`, `bus`, `truck`, `ambulance`, `fire_truck`, dengan ID ByteTrack per kamera. ATCS mengambil frame asli yang persis sama dengan frame tracking saat hasilnya mutakhir. Pergantian mode tidak memulai ulang sumber. Rekaman otomatis berjalan dari awal saat backend dimulai dan looping; setiap loop mereset tracker/waktu tunggu sambil mempertahankan identitas sumber serta kalibrasi. Unggahan baru atau pergantian CCTV membuat sumber dan tracker baru. Video asli tetap tersedia saat inferensi gagal, dengan status gangguan.

Frame hasil memiliki nomor frame dan waktu media sendiri; kotak digambar langsung pada frame yang dianalisis. Frame terlambat lebih dari tiga detik tidak ditampilkan sebagai deteksi baru. Tombol jeda/ulang/jalankan rekaman telah dihapus. Status menampilkan throughput pemrosesan dan laju hasil tracking tiap kamera secara terpisah. Empat kamera berbagi satu model, masing-masing memiliki tracker dan penghitung ID sendiri; antrian dibatasi satu pekerjaan tiap kamera dan pekerjaan lama dilewati. Buffer kehilangan ID dua detik dihitung dari waktu sumber, termasuk frame yang terlewat. Objek yang tertutup lama dapat mendapat ID baru.

Saat menunggu giliran model, pekerjaan kamera mengambil JPEG terbaru setelah memperoleh giliran, bukan menyimpan frame lama selama antrean. Frame asli dan overlay tetap memakai sampel yang sama. Worker memilih GPU secara otomatis bila runtime CUDA tersedia; backend memakai environment terpisah dari vision.

## Pemasangan lokal

Backend tetap menggunakan `.venv` Python 3.14. Worker vision menggunakan Python 3.12 atau 3.13 terpisah. Contoh CPU:

```powershell
py -3.12 -m venv work/vision-env
.\work\vision-env\Scripts\python.exe -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
.\work\vision-env\Scripts\python.exe -m pip install -r vision/requirements.txt
```

Untuk GPU gunakan build PyTorch resmi yang sesuai CUDA perangkat. Jangan mengganti dependensi backend. Simpan model terlatih `best.pt` di `models/sigap_yolo26s/best.pt`. Model dan video tidak masuk Git. Tambahkan ke `.env` lokal:

```dotenv
SIGAP_YOLO_ENABLED=true
SIGAP_YOLO_MODEL=models/sigap_yolo26s/best.pt
SIGAP_VISION_PYTHON=C:/path/proyek/work/vision-env/Scripts/python.exe
```

Runtime yang berhasil diuji pada RTX 2050 4 GB / driver 581.29 menggunakan wheel Windows Python 3.12 `torch==2.14.1+cu130` dan `torchvision==0.29.1+cu130`, dari [indeks resmi PyTorch CUDA 13.0](https://download.pytorch.org/whl/cu130/). Hentikan worker vision sebelum mengganti paket; gunakan runtime vision terpisah, lalu pastikan `torch.cuda.is_available()` bernilai `True`. Pilih build lain bila GPU/driver berbeda.

Restart backend; sumber tersimpan langsung berjalan. Untuk mengganti video pilih U/T/S/B lalu unggah MP4 maksimal 256 MB melalui panel CCTV. Penggantian sumber menghapus kalibrasi lama sehingga video baru perlu ditandai ulang. Log worker ada di `work/runtime/vision.log`. Worker CPU hanya memakai dua thread PyTorch. Satu worker backend diperlukan. Compose bawaan belum memuat runtime vision; petunjuk ini untuk proses lokal. [Pengukuran dan kendali video](video-control.md).

## Hasil uji 5 Oktober 2026

Model `sigap_yolo26s_stage6_v2_20261005/best.pt`, SHA256 `d4d3efa70255ba9cb43ae71edccc6a2f519d12ffcc44884b475e40862e2bcbe2`. Uji Colab Tesla T4, ukuran inferensi 640, confidence minimum 0,1, ByteTrack high 0,25 / low 0,1 / new 0,35 / match 0,8. Lima inferensi pemanasan, lalu semua frame video 30 FPS diproses tanpa stride.

| Kamera | Frame | YOLO + ByteTrack + plot + JPEG | Baca + tracking + tulis MP4 |
|---|---:|---:|---:|
| U | 616 | 25,73 FPS | 18,93 FPS |
| T | 651 | 24,65 FPS | 18,32 FPS |
| S | 604 | 27,20 FPS | 19,90 FPS |
| B | 609 | 27,66 FPS | 20,18 FPS |

Pengujian dilakukan berurutan, bukan empat kamera 30 FPS bersamaan. Konversi MP4 ke H264 setelah pemrosesan tidak masuk angka throughput. Video hasil empat kamera disimpan dalam folder run Drive bersama `tracking_benchmark.json` dan `tracking_review.jpg`.

Uji worker lokal CPU, frame JPEG 640 dari empat kamera secara bergantian, tujuh pengamatan terukur tiap kamera setelah frame awal: U 21,03 / T 20,47 / S 16,47 / B 20,33 FPS. Angka ini throughput per pekerjaan, bukan FPS setiap kamera ketika empat kamera aktif bersamaan. Pratinjau aplikasi tetap maksimal **5 FPS**, mengikuti decoder bersama yang sudah ada. Kecepatan aktual di halaman dihitung dari hasil yang benar-benar selesai.

Pemeriksaan visual pada 5 Oktober menunjukkan kotak dan ID pada kendaraan utama di empat video. Motor kecil/padat dan objek tertutup masih dapat lolos atau berganti ID. Retensi ID antara frame yang diukur 0,984–0,990 hanya deskriptif, **bukan IDF1 atau akurasi ground truth**. Klip ambulans/pemadam belum diuji sesuai keputusan pengguna. Integrasi antrean/waktu tunggu dan kendali tersedia setelah kalibrasi; pemicu EVP video masih belum diaktifkan.

Uji tambahan empat decoder 5 FPS secara bersamaan pada CPU lokal menunjukkan hasil tracking U 4,68 / T 3,25 / S 3,26 / B 3,63 FPS, dengan usia frame hasil 0,26–0,44 detik. Keempat kamera menerima kotak dan ID. Beban mesin lain dan pemanasan dapat memengaruhi hasil; throughput yang tampil di halaman mengabaikan hasil pertama tiap kamera agar pemanasan tidak mengaburkan angka. Pada satu kamera U, halaman menampilkan 5 FPS tracking dan sekitar 17–18 FPS pemrosesan.

Verifikasi: 221 tes backend lulus, satu tes PostgreSQL dilewati karena konfigurasi database uji tidak disediakan; 68 tes frontend lulus, typecheck dan build lulus. Uji nyata worker memeriksa kecocokan sesi/frame dan ID unik pada empat sumber. Skrip `python -m vision.benchmark` dapat mengulang pengukuran singkat setelah paket sumber diletakkan di `work/tracking-review`.

## Verifikasi perubahan 6 Oktober 2026

Versi auto-video/kendali: **228 tes backend**, **69 tes frontend**, typecheck/build, dan pemeriksaan kontrak lulus. Satu tes PostgreSQL tetap dilewati karena konfigurasi database uji tidak tersedia.

Uji aplikasi berjalan dengan empat sumber pada RTX 2050: U **2,12**, T **2,16**, S **2,10**, B **2,15 FPS tracking**; usia frame hasil **0,28–0,63 detik**. Semua sumber telah berulang otomatis dan pasangan frame ATCS/SIGAP cocok sesi, nomor frame, dan waktu medianya. Angka ini sampel runtime bersama, bukan jaminan FPS stabil untuk video/perangkat lain. Pengukuran CPU sebelumnya hanya **0,33–0,46 FPS per kamera**, sehingga paket CUDA dipasang ke runtime vision. Model dan ukuran inferensi 640 tidak diubah.

Keempat sumber utama belum memiliki kalibrasi, sehingga status adaptif benar-benar menolak pengambilalihan dan memberikan alasan tiap pendekat. Aktivasi, fallback, pemulihan otomatis, pelepasan manual, serta kesesuaian peta/fase diverifikasi lewat tes integrasi; kalibrasi video sebenarnya dan perbandingan pengamatan manual masih diperlukan. Klip EVP belum diuji.
