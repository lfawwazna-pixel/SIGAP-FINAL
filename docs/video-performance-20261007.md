# Pemeriksaan performa empat kamera, 7 Oktober 2026

Perubahan ini mengurangi pekerjaan CPU dan permintaan web yang tidak diperlukan.
Model, resolusi inferensi 640, confidence 0.1, ByteTrack, preview 5 FPS, TTL data
3 detik, autentikasi setiap permintaan, dan logika keselamatan ATCS tetap sama.

## Perubahan

- FFmpeg membatasi filter video ke satu thread per kamera, selain batas thread
  decoder dan encoder yang sudah tersedia.
- OpenCV memakai satu thread; PyTorch tetap dua thread. Empat decoder, database,
  backend, dan ATCS berbagi CPU laptop.
- Monitor berhenti mengambil posisi kendaraan sintetis saat peta memakai hasil
  video atau ruang simulasi terpisah ditampilkan. Status pengendali ATCS tetap
  diperiksa. Permintaan posisi sintetis kembali saat baseline ATCS ditampilkan.
- `SIGAP_VISION_DIAGNOSTICS=1` mengaktifkan ringkasan waktu decode, model,
  tracking, serta gambar keluaran setiap sekitar 10 detik. Ringkasan hanya
  ditulis ke stderr worker, tanpa gambar, token, alamat kamera, atau kredensial.
  Transport stdout JSON tetap bersih. Diagnostik mati secara default.

## Validasi

- 52 tes backend terkait video, tracking, pengukuran, kendali dan adaptif lulus.
- 73 tes frontend lulus, termasuk peta dengan takeover, polling ATCS yang terus
  berlangsung, polling sintetis yang berhenti dan kembali, serta ruang simulasi.
- Kontrak, typecheck dan build produksi lulus (`index-C4Tc3Zjp.js`).
- Pengujian performa memakai empat MP4 terbaru, GPU RTX 2050, database PostgreSQL
  khusus `sigap_test`, login normal, seluruh middleware dan endpoint backend.
  Akun uji dibuat sementara dan dihapus setelah selesai; akun operator tidak diubah.
- Dengan beban polling website selama 30 detik, setiap kamera menghasilkan
  sekitar 4.99–5.02 FPS, tanpa sampel kamera kedaluwarsa. 481 permintaan HTTP
  menghasilkan 200. Pada fase tanpa polling posisi sintetis, 374 permintaan
  menghasilkan 200, tanpa sampel kamera kedaluwarsa.
- Waktu worker rata-rata pada fase polling lengkap: sebelum 24.16 ms, sesudah
  20.91 ms. Usia tracking rata-rata sebelum 64.70 ms, sesudah 53.18 ms.
  Ini perbandingan singkat pada laptop yang sama, bukan jaminan peningkatan
  pada setiap beban, suhu, atau perangkat. Sebelum perubahan pun tes ini sudah
  mencapai 5 FPS; penurunan 1–1.8 FPS dari pengamatan browser sebelumnya belum
  berhasil direproduksi dalam pengujian ini.
- Uji pipeline terpisah memeriksa jumlah ikon per pendekat sama dengan track
  mutakhir, tampilan tanpa kalibrasi tidak membuat demand, takeover/fase aktual,
  kamera gagal, fallback, pemulihan otomatis, EOF/loop dengan tracker baru,
  serta pelepasan manual yang tetap di ATCS.

## Bukti dan batas pemeriksaan

Laporan terstruktur terdapat di `work/performance/application-profile.json`,
`application-candidate.json`, dan `worker-profile.json`. Laporan integrasi
terdapat di `work/performance/pipeline-report.json`.

Tes performa menggunakan route aplikasi melalui ASGI, bukan rendering browser.
Browser tidak dapat menjangkau preview yang diluncurkan dari sesi Windows
terbatas ini. Pemeriksaan langsung setelah pemasangan masih harus dilakukan
dengan layanan dari terminal pengguna. Installer membuka jendela uji 600 detik
dan menyimpan log di `work/runtime/performance-preview`; diagnostik worker
terdapat di `work/runtime/vision.log`. Selesai jendela uji, layanan aplikasi dan
worker GPU milik installer dihentikan, sedangkan database tetap tersedia.

Deteksi motor kecil/padat pada kamera Selatan serta akurasi ambulans/pemadam
belum dinyatakan lulus. Perubahan ini tidak mengganti hasil deteksi dengan
kendaraan buatan dan tidak melatih atau mengganti model.

