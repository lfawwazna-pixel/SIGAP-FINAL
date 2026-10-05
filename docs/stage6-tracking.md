# Video YOLO26s dan ByteTrack

SIGAP menampilkan hasil model enam kelas `car`, `motorcycle`, `bus`, `truck`, `ambulance`, `fire_truck`, dengan ID ByteTrack per kamera dan sesi. ATCS mengambil frame asli dari decoder yang sama. Pergantian mode tidak memulai ulang sumber. Restart rekaman, unggahan baru, atau pergantian CCTV membuat sesi dan tracker baru. Tidak ada deteksi palsu saat model belum tersedia atau inferensi gagal: video asli tetap tersedia dan status gangguan ditampilkan.

Frame hasil memiliki nomor frame dan waktu media sendiri; kotak digambar langsung pada frame yang dianalisis. Frame terlambat lebih dari tiga detik tidak ditampilkan sebagai deteksi baru. Saat dijeda, overlay hanya dipakai apabila cocok dengan frame terakhir. Status menampilkan throughput pemrosesan dan laju hasil tracking tiap kamera secara terpisah. Empat kamera berbagi satu model, masing-masing memiliki tracker dan penghitung ID sendiri; antrian dibatasi satu pekerjaan tiap kamera dan pekerjaan lama dilewati. Buffer kehilangan ID dua detik dihitung dari waktu sumber, termasuk frame yang terlewat. Objek yang tertutup lama dapat mendapat ID baru.

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

Restart backend lalu jalankan sumber video melalui panel CCTV. Log worker ada di `work/runtime/vision.log`. Worker CPU hanya memakai dua thread PyTorch. Satu worker backend diperlukan, sesuai desain eksperimen dan decoder bersama yang sudah ada. Compose bawaan belum memuat runtime vision; petunjuk ini untuk proses lokal.

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

Pemeriksaan visual menunjukkan kotak dan ID pada kendaraan utama di empat video. Motor kecil/padat dan objek tertutup masih dapat lolos atau berganti ID. Retensi ID antara frame yang diukur 0,984–0,990 hanya deskriptif, **bukan IDF1 atau akurasi ground truth**. Klip ambulans/pemadam belum diuji sesuai keputusan pengguna. Tracking ini belum menjadi sumber pengukuran antrean/waktu tunggu atau pemicu EVP/kendali lampu; integrasi tersebut tetap tahap berikutnya.

Uji tambahan empat decoder 5 FPS secara bersamaan pada CPU lokal menunjukkan hasil tracking U 4,68 / T 3,25 / S 3,26 / B 3,63 FPS, dengan usia frame hasil 0,26–0,44 detik. Keempat kamera menerima kotak dan ID. Beban mesin lain dan pemanasan dapat memengaruhi hasil; throughput yang tampil di halaman mengabaikan hasil pertama tiap kamera agar pemanasan tidak mengaburkan angka. Pada satu kamera U, halaman menampilkan 5 FPS tracking dan sekitar 17–18 FPS pemrosesan.

Verifikasi: 221 tes backend lulus, satu tes PostgreSQL dilewati karena konfigurasi database uji tidak disediakan; 68 tes frontend lulus, typecheck dan build lulus. Uji nyata worker memeriksa kecocokan sesi/frame dan ID unik pada empat sumber. Skrip `python -m vision.benchmark` dapat mengulang pengukuran singkat setelah paket sumber diletakkan di `work/tracking-review`.
