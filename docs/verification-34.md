# Verifikasi Tahap 3 dan 4

Tanggal pengguna: **4 Oktober 2026**, Asia/Jakarta. Proyek: `C:\Users\Muhammad Luthfi Fawwazna\Project\PROJECT-SIGAP-ASTRA`.

| Pemeriksaan | Hasil |
|---|---|
| Python/backend | **124 tes lulus**, tanpa skip; termasuk database PostgreSQL nyata |
| Frontend | **53 tes lulus**, enam berkas |
| TypeScript / Vite production build | Lulus |
| JSON Schema / tipe frontend | Sinkron; mode schema input dan respons sesuai |
| Migrasi database | Tidak ada perubahan skema yang belum dimigrasikan |
| Compose | Konfigurasi valid; PostgreSQL sehat |
| Proses ATCS dan pengirim terpisah | Tiga skenario lulus: pengirim dimatikan, data membeku, pelepasan manual |
| Alur aplikasi melalui Vite | Login → status kendali → aktivasi tanpa sumber ditolak → ATCS tetap berjalan → logout lulus |
| Rahasia antarlayanan | Dikonfigurasi lokal; tidak ditemukan di bundle browser |
| Pemeriksaan visual browser | Belum dilakukan; izin Browser Use tersimpan memblokir localhost |

Satu peringatan deprecation Starlette TestClient/httpx tetap ada. Tidak ada dependency atau migrasi database baru. Build image aplikasi Compose/deployment tidak dilakukan; layanan diuji sebagai proses pengembangan lokal.

## Perilaku yang dibuktikan

- Aktivasi tidak menerapkan hijau langsung. Minimum hijau, kuning penuh, semua merah, occupied/unknown conflict dan pelepasan clearance diuji dengan jam deterministik.
- Receipt accepted dibedakan dari applied. Rencana yang diganti menjadi cancelled; rencana dengan sisa masa berlaku kurang dari hijau penuh dibatalkan.
- Heartbeat hilang dan data kedaluwarsa diuji terpisah. Frame dengan timestamp sama tidak dapat memperbarui umur data walaupun heartbeat tetap datang.
- Durasi hijau di luar batas, command terlambat, sequence lama, revision lama, run salah, sesi dicabut dan bentuk action salah ditolak.
- Duplikat perintah tidak memperpanjang heartbeat atau membuat sesi baru. Isi berbeda dengan request ID sama ditolak.
- Pergantian proses sumber mencabut kendali lama. Koreksi jam kalender tidak memperpanjang deadline monotonic yang telah dibuat.
- Tidak ada rencana awal/berikutnya memicu fallback. SIGAP tidak diaktifkan ulang hanya karena data pulih.
- Test dua proses mematikan pengirim dan memberi jeda tanpa polling selama delapan detik. ATCS tetap bertransisi dan kembali fixed-time pada run yang sama; sesi lama tidak dapat digunakan kembali.
- Pengirim yang masih hidup dengan frame membeku juga memicu fallback. Pelepasan manual berakhir pada receipt applied setelah transisi aman.
- Proteksi sesi, izin control:operate, origin, CSRF, bearer key, redaksi pesan error serta validasi identitas upstream diuji.
- Kehilangan respons POST tidak menghasilkan klaim berhasil. Retry server menggunakan envelope yang sama; dashboard memeriksa tanda terima tanpa mengirim ulang otomatis.
- UI menonaktifkan tindakan saat sumber belum siap, hanya sumber uji yang tersedia, akun tidak berizin, koneksi putus, respons membeku, atau halaman tersembunyi. Status accepted/applied/cancelled ditampilkan terpisah.
- Regresi Simulasi 2F membuktikan pause/start/reset/kecepatan/spawn hanya memengaruhi eksperimen. ATCS utama tidak direset oleh perpindahan tab atau tindakan percobaan.

## Keadaan pratinjau setelah verifikasi

Frontend `http://127.0.0.1:5173`, backend port 8000, ATCS port 8001, PostgreSQL port 5432. Instance utama menjalankan fixed-time, `ATCS_ENABLE_TEST_SOURCE=false`, dan belum menerima sumber CCTV. Aktivasi tanpa sumber mendapat 409 NOT_READY. Sesi uji login telah diakhiri. Password operator dan database tidak diganti; `.env` mendapat rahasia komunikasi baru yang tidak ditampilkan.

Backup source sebelum pengerjaan berada pada `C:\Users\Pongo\Documents\Codex\2026-10-03\say\work\backup-before-34`. Log pratinjau berada pada `C:\Users\Pongo\Documents\Codex\2026-10-03\say\work\sigap-34-preview`. Folder cadangan mengecualikan rahasia, data database dan dependency.

## Batas hasil

Ini pengujian integrasi perangkat lunak terhadap ATCS tiruan, bukan sertifikasi perangkat lalu lintas. Kendaraan pada ATCS utama masih sintetis. Lab menggunakan timer fixture lebih singkat dan area konflik diasumsikan kosong; kasus occupied/unknown diuji terpisah pada mesin deterministik, sedangkan regresi kendaraan memeriksa conflict provider sebenarnya pada prototipe. Kunci layanan mempercayai pelapor kualitas data; evaluasi CCTV nyata tetap pekerjaan Tahap 6–7.

UI diuji dengan jsdom untuk struktur, aksesibilitas dasar dan interaksi, belum dengan inspeksi piksel di browser. Riwayat kontrol dan tanda terima disimpan dalam memori dengan retensi terbatas. Backend/ATCS tetap satu worker. Pekerjaan berhenti pada Tahap 3/4; heuristik operasional Tahap 5 serta YOLO/EVP operasional belum dikerjakan.

Panduan menjalankan ulang skenario dan spesifikasi protokol: [Integrasi SIGAP–ATCS](control-integration.md).
