# Penerimaan EVP v6 — 8 Oktober 2026

## Hasil software

- Suite backend: 315 lulus; satu tes PostgreSQL opt-in dilewati pada suite umum. Tes PostgreSQL tersebut kemudian dijalankan secara terpisah pada database sigap_evp_v6_test dan lulus: total 316 tes lulus.
- Frontend: 96 tes lulus pada 14 file. Panel EVP dan panel mutu model termasuk di dalamnya.
- Kontrak data, TypeScript dan build produksi lulus.
- Koneksi database aplikasi pengguna berhasil; akun dan kata sandi pengguna tidak diubah.
- Kalibrasi U: target pada detik 60/80/90/95 berada pada lajur middle; pada 98 detik kotak kendaraan sedang melintasi garis henti. Penyelesaian prioritas menunggu kotak sepenuhnya lewat atau bukti hilang.

Pengujian deterministik memakai waktu buatan untuk membuktikan urutan dan batas; bukan mengklaim semua kondisi kamera/aktivasi sirene sudah tervalidasi. Hasil pelatihan dan pemeriksaan runtime ditambahkan setelah model selesai dievaluasi.

## Artefak pelatihan

Training dihentikan melalui Interrupt execution sesudah 41 epoch selesai dan tersimpan (epoch 42 belum selesai). Durasi sekitar 1 jam 39 menit. Checkpoint terbaik sekitar epoch 18 dipilih; bukan bobot parsial dari epoch yang diinterupsi. File best.pt telah tersedia lokal dan hash-nya telah diverifikasi. File yang diwajibkan sebelum pemasangan: best.pt, evaluation.json, model-card.json, runtime-frame-audit.json. SHA256 best.pt harus sesuai model-card.json. Paket baru disimpan sebagai versi terpisah sehingga model sebelumnya tetap tersedia.

## Penerimaan runtime yang harus dicatat

1. Empat sumber video aktif dan timestamp tracking baru; model dan hash sesuai evaluasi.
2. Ambulans pada target klip U dikenali sebagai ambulance, bukan dipaksa melalui pergantian nama car.
3. Kandidat terkonfirmasi beberapa frame; permintaan prioritas hanya sesudah SIGAP aktif dan kalibrasi siap.
4. Minimum hijau, kuning, semua merah dan clearance berlangsung; tidak ada dua pendekat hijau bersamaan.
5. Target lewat/hilang membatalkan prioritas dan keputusan adaptif kembali tersedia.
6. Deteksi kendaraan biasa tetap menjadi pengamatan latar; overlay berfokus pada EVP saat pelayanan.
7. Login, panel mutu model, riwayat kejadian dan model lama sebagai cadangan tetap tersedia.

Lihat [aturan dan batas](evp-video-v6.md). Pengukuran manual lengkap antrean/waktu tunggu pada empat kamera serta rekaman pemadam nyata masih diperlukan sebelum klaim validasi lapangan 100%.

## Hasil evaluasi Colab

Model baseline dan kandidat diuji dengan imgsz=640, conf=0,25 pada split publik 811 gambar yang sama. mAP50 umum: 65,40% → 64,81%; mAP50–95: 49,75% → 49,24%. Tidak semua kelas membaik: truck mAP50 turun dari 52,11% menjadi 32,07%, sementara motorcycle naik 44,16% → 49,16%, bus 75,23% → 82,90%, ambulance 71,98% → 72,23%, dan fire_truck 67,11% → 73,88%. Regresi kelas truk tetap dilaporkan.

Pada 12 frame review temporal klip yang sama, recall ambulance 0% → 100% dan mAP50 0% → 99,5%. Ini adalah review klip yang sama dengan label bantu; bukan akurasi lapangan 100%, bukan uji kamera independen, dan bukan verifikasi sirene.

Pemeriksaan target pada delapan frame yang lebih jelas (70, 76, 78, 80, 90, 92, 95, 98 detik): baseline menyebut car pada semuanya; best menyebut ambulance dengan confidence 82,7–97,0%. Audit awal juga mencantumkan detik 60; target pada frame itu sebagian tertutup dan anchor terlalu besar/ambigu sehingga tidak dipakai sebagai bukti positif yang pasti. Raw audit tetap disimpan supaya keterbatasannya bisa ditelusuri.

Checkpoint: models/sigap_yolo26s_evp_v6_20261008/best.pt. Artefak Drive mencakup best/last, evaluation.json, model-card.json, audit target dan konfigurasi training. Hash deployment harus sesuai model-card. Hasil lokal saat runtime belum diklaim sebelum diuji.

## Uji lokal seluruh klip dan replay kendali

Seluruh 108,4 detik klip (542 frame pada sampling 5 FPS) diproses dengan decoder dan worker SIGAP yang sama. Ditemukan prediksi car/ambulance ganda dengan kotak hampir identik. Penyaringan sebelum ByteTrack mempertahankan prediksi dengan confidence tertinggi; tidak mengganti kelas car menjadi ambulance. Kotak harus sangat bertumpang tindih, pusatnya sejajar dan ukurannya sebanding, agar kendaraan bersebelahan tetap terpisah.

Sesudah perbaikan, target ambulance memiliki satu ID stabil (153 pada sesi benchmark ini), 143 pengamatan segar dengan confidence ≥0,6 antara 67,2–98,4 detik; jeda bukti terpanjang 0,8 detik. Memori coasted tidak dipakai untuk mengonfirmasi EVP. Nomor ID dapat berbeda pada sesi lain.

Replay jejak deteksi nyata memakai kalibrasi U yang tersimpan, sender, dan pengendali lampu dengan waktu deterministik. Satu target dikonfirmasi pada sekitar detik 68, dilayani di U sesudah minimum hijau, kuning dan semua merah; prioritas dilepas sekitar 99,8 detik dan adaptif normal melayani S sekitar 105 detik. Sebanyak 642 snapshot tidak menghasilkan dua sinyal hijau bersamaan. Provider konflik pada replay ini sengaja clear; tes terpisah mencakup occupied dan unknown. Replay bukan pembuktian lampu lapangan atau aktivasi sirene.

GPU lokal: rata-rata worker setelah startup 20,835 ms/frame (p95 23,368 ms), sekitar 48,0 FPS pemrosesan offline untuk satu klip. Ini bukan FPS tayangan atau throughput empat kamera bersamaan. Semua artefak benchmark dan replay disimpan di work/evp-20261008/runtime-evaluation-fixed pada workspace pengujian.

Paket pemasangan harus diterapkan dan website dijalankan sebelum pemeriksaan tampilan langsung dinyatakan selesai.

## Pembacaan bukti setiap frame

Uji website mengungkap pembacaan kandidat lewat polling HTTP 0,5 detik dapat melewatkan klasifikasi segar di antara polling. Bukti EVP kini diperbarui langsung sesudah hasil tracking yang sah diterima. Frame yang terlambat sesudah pergantian sumber/tracker tidak memanggil observer. Permintaan lampu tetap memakai urutan perintah dan watchdog yang sama; waktu atau kelas tidak dimanipulasi. Pengujian callback dan replay kendali dengan polling 0,6 detik membuktikan bukti kamera tetap terpakai di antara polling.
