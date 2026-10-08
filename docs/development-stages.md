# Tahapan SIGAP — 8 Oktober 2026

Penomoran ini mengikuti tabel tugas pengguna: 2C login, 2D monitor. Catatan lama memakai 2C monitor/2D login dan disimpan di [riwayat implementasi](development-history.md); status historis seperti “CCTV belum terhubung” tidak menggambarkan versi sekarang.

| Tahap | Implementasi saat ini | Bukti penyelesaian dan batas |
|---|---|---|
| 1 Spesifikasi | Geometri, baseline 450 detik, ATCS–SIGAP, video dan EVP terdokumentasi | docs/specification.md dan evp-video-v6.md; lampu lapangan belum terhubung |
| 2A Fondasi | FastAPI, React/TypeScript, PostgreSQL, kontrak dan Compose | Build, kontrak, tes; database lokal tetap diperlukan |
| 2B ATCS | Timer mandiri U–T–S–B, kuning/clearance | Tes fase dan independensi proses |
| 2C Login | Akun operator, sesi, CSRF, logout, pembatasan akses | Tes autentikasi; akun/kata sandi tidak diubah oleh pemasangan EVP |
| 2D Monitor | Peta, kamera, countdown, riwayat, status kendali | API menjadi sumber status; UI tidak mengarang fase |
| 2E Simulasi | Tiga lajur, gerakan kendaraan, antrean, konflik | Tes geometris dan simulasi |
| 2F Kontrol | ATCS/SIGAP/simulasi, kontrol percobaan, EVP sintetis | Kontrol waktu simulasi tidak mengubah jam pengendali operasional |
| 3 Integrasi tiruan | Sesi, perintah, urutan, heartbeat | Valid/ulang/basi/salah diuji |
| 4 Override/fallback | Pengambilalihan dan pemulihan | Watchdog ATCS mandiri; transisi aman diuji |
| 5 Adaptif sintetis | Kebijakan, pemerataan, eksperimen berpasangan | Hasil simulasi diberi label sumber |
| 6A Pelatihan | Model enam kelas + fine-tuning ambulans v6 dengan batas waktu | Per kelas dan hash model tersedia sesudah evaluasi; same-video bukan uji kamera independen |
| 6B Tracking | YOLO + ByteTrack, kestabilan ID, hitungan dan ROI | Tes transport/coasting; hitungan padat/antrean/waktu tunggu manual belum seluruhnya tervalidasi |
| 6C Empat pendekat | Empat video otomatis/looping dan kalibrasi per kamera | Sumber/data basi/sesi/loop dikenali; kamera berbeda bukan empat rekaman lapangan serentak |
| 7 AI–kontrol | Pengukuran video, adaptif, override dan fallback | Tes sender–pengendali; uji model baru saat runtime dicatat pada laporan validasi |
| 8 EVP | Kandidat temporal, kunci target, prioritas, clearance, pemulihan | Fokus utama v6; tes ambulans/pemadam empat arah; bukti ambulans nyata pada klip, pemadam nyata belum tersedia |
| 9 Dashboard | Monitor, mutu model per kelas, EVP, analytics, riwayat | Angka hilang tidak ditampilkan sebagai nol; sumber dan keterbatasan ditampilkan |
| 10 Evaluasi | Eksperimen sintetis, model-card, baseline vs candidate, protokol penerimaan | Klaim perbaikan di jalan memerlukan percobaan nyata yang setara dan anotasi manual |

Tidak ada persentase 100% untuk akurasi/dampak lapangan tanpa bukti. Penyelesaian software dibedakan dari validasi empiris. Lihat [alur EVP](evp-video-v6.md) dan [hasil pengujian](evp-validation-v6.md).
