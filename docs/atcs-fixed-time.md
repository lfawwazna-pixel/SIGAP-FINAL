# Pengendali ATCS fixed-time — Tahap 2B

Implementasi ini menjalankan pengendali simulasi, tanpa sambungan perangkat lampu lapangan. Pengendali menggunakan konfigurasi resmi proyek dan tetap hidup tanpa backend, browser, serta database.

## Menjalankan ATCS saja

Dari root PROJECT-SIGAP-ASTRA, setelah dependency Python terpasang:

```powershell
.\.venv\Scripts\python.exe -m uvicorn atcs_simulator.app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

Tidak perlu mengisi password PostgreSQL untuk menjalankan ATCS. Baca GET http://127.0.0.1:8001/status, /health, atau /events. Dokumentasi interaktif API ada pada /docs. GET hanya membaca; menutup halaman tidak menghentikan timer. Hentikan proses dengan Ctrl+C.

## Aturan fase

```text
Startup / restart
    → semua merah minimum 2 detik
    → tunggu area konflik kosong jika diperlukan
    → U hijau 85 → U kuning 3 → semua merah ≥2
    → T hijau 150 → T kuning 3 → semua merah ≥2
    → S hijau 95 → S kuning 3 → semua merah ≥2
    → B hijau 100 → B kuning 3 → semua merah ≥2
    → kembali U
```

Angka berasal dari configs/intersection.json, tidak ditanam ulang di engine. Diagram menjelaskan baseline; jika konfigurasi valid berubah, engine mengikutinya setelah restart.

Pada jam uji ideal, hijau U pertama dimulai pada detik 2 dan berikutnya pada detik 452: siklus U-ke-U **450 detik**, di luar clearance startup 2 detik. Waktu aktual bisa lebih panjang karena penahanan konflik atau penjadwalan proses.

Saat tick terlambat, engine melakukan paling banyak satu transisi pada tick itu dan memberikan durasi penuh untuk fase baru. Misalnya hijau yang terlambat selesai tetap melewati kuning penuh 3 detik, lalu semua merah minimum. Engine tidak mengejar waktu dengan melewati beberapa fase sekaligus atau memotong kuning.

Hanya satu pendekat bersinyal boleh hijau/kuning; lainnya merah. Pada semua merah active_approach null dan keempat sinyal merah. Ruas pintas kiri tetap mengikuti spesifikasi geometri; kendaraan sintetis telah ditambahkan pada Tahap 2E.

## Jam, sesi dan restart

- Jam monotonic menentukan durasi; UTC digunakan untuk cap waktu. Pergeseran jam komputer tidak memperpendek fase.
- Laju waktu runtime 1:1, pembaruan target 100 ms. Scheduler sistem operasi dapat menyebabkan keterlambatan.
- UUID run_id baru dibuat pada startup. Waktu simulasi dan nomor snapshot mulai dari 0; nomor event mulai dari 1.
- Shutdown normal mencatat state terminal semua merah dan service_stopped dalam buffer, lalu menghentikan task. Buffer hilang ketika proses berakhir; tidak ada penyimpanan sesi otomatis.
- Restart selalu memulai clearance semua merah sebelum pendekat pertama. Tidak memulihkan hitungan mundur lama.
- Kesalahan task dicatat sebagai fault dan tidak otomatis melanjutkan fase. Proses API dapat tetap hidup dengan status 503. Tidak ada perintah reset via HTTP; restart proses membuat sesi baru.

Penghentian proses atau listrik host bukan mekanisme kendali perangkat lampu. Semua merah terminal di sini adalah state simulasi, bukan jaminan keluaran fisik.

## Input area konflik

Sejak Tahap 2E, default ConflictProvider adalah TrafficWorld dengan sumber provider. Keterisian berasal dari kendaraan sintetis yang sudah masuk dan belum keluar dari area konflik. AssumedClear tetap tersedia sebagai provider pengujian, bukan default aplikasi. Tidak ada deteksi CCTV pada tahap ini.

ConflictProvider menyediakan read() yang mengembalikan clear/occupied/unknown dan source provider. Provider adalah pembacaan lokal yang cepat, tidak boleh melakukan I/O jaringan atau menunggu proses lain. Provider dipasang melalui dependency Python create_app(conflict_provider=...) ketika simulator kendaraan diintegrasikan; tidak ada endpoint publik untuk memaksa clear.

Kegagalan/hasil tidak valid dari provider menjadi unknown. Pada semua merah, engine tetap menyelesaikan durasi minimum, kemudian menunggu clear. Selama menunggu: clearance_state waiting_conflict, remaining_seconds null. Saat clear tiba, hijau berikutnya mulai dengan durasi penuh dan urutan pendekat tetap terjaga.

Occupied pada hijau/kuning bukan alasan untuk langsung memotong fase: kendaraan yang sudah masuk perlu menyelesaikan gerakannya. Pemeriksaan pelepasan pendekat baru berlangsung pada semua merah. Validasi umur pengukuran kamera akan ditambahkan ketika sumber tersebut tersedia.

## Riwayat

Buffer menyimpan 1.000 kejadian terbaru per sesi, tanpa database. Kejadian memuat fase/pendekat sebelum dan sesudah, alasan, waktu, ID sesi, dan nomor event. Penahanan tidak menambahkan event berulang pada setiap tick; ada event saat mulai ditahan dan saat dilepas.

GET /events?after=0&limit=100 membaca halaman pertama. Pembacaan berikutnya memakai next_after dan run_id dari respons. Sesi baru ditandai run_changed; riwayat yang sudah terbuang ditandai history_truncated. Ketika has_more true, lanjutkan halaman sampai selesai. Rincian ada di [kontrak data](contracts.md).

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_engine.py tests/test_runtime.py tests/test_services.py
.\.venv\Scripts\python.exe -m pytest -q -m process
```

Tes engine memeriksa baseline 450 detik, seluruh batas fase, sinyal eksklusif, konflik/unknown, scheduler terlambat, koreksi UTC, clock invalid, restart, retensi/cursor dan status rusak. Jam dikendalikan tes sehingga tidak perlu menunggu 7,5 menit.

Tes proses memakai **file konfigurasi pengujian sementara** dengan fase pendek, port localhost sementara, dan dua proses Uvicorn sungguhan. Backend dihentikan, tidak ada polling selama 4,2 detik, kemudian tes memastikan ATCS tetap menghitung dan mencatat beberapa pergantian. Konfigurasi resmi 85/150/95/100 tidak diubah. Tes juga memverifikasi ID sesi berubah setelah proses ATCS direstart. Seluruh proses uji ditutup setelah tes.

## Batas tahap

Peta ditambahkan pada 2C, akun pada 2D, kendaraan/antrean serta eksperimen pada 2E/2F. Sejak 3/4, ManagedEngine membungkus baseline FixedTimeEngine dengan sesi override, watchdog dan transisi fallback; sumber konflik utama tetap kendaraan sintetis. Baseline tetap menjadi default. Rincian pengambilalihan, pengembalian urutan dan uji proses: [Integrasi kendali](control-integration.md). Heuristik adaptif/EVP masih berada pada eksperimen terpisah; YOLO dan deployment belum tersedia. Satu worker/instance ATCS per simpang wajib digunakan karena state belum dibagikan ke proses lain. Riwayat belum persisten.

Implementasi memakai [lifespan FastAPI](https://fastapi.tiangolo.com/advanced/events/) untuk umur task, [task asyncio](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task) untuk loop mandiri, dan [jam monotonic Python](https://docs.python.org/3/library/time.html#time.monotonic) untuk durasi.
