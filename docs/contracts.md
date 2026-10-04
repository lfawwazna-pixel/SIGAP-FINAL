# Kontrak data ATCS dan operator sampai Tahap 4

Sumber definisi: `contracts/models.py`, `contracts/traffic.py`, dan `contracts/control.py`. JSON Schema pada `contracts/schemas/` serta tipe/schema frontend merupakan hasil generasi dari sumber tersebut. Konfigurasi persimpangan tetap satu file; schema bukan salinan waktu lampu yang terpisah. Kontrak input memakai schema validation; kontrak respons memakai schema serialization. Aturan kondisional per action diperiksa validator Python.

Revisi tiga lajur memakai `IntersectionConfig.schema_version=2.0`: `outer.left`, `middle.straight`, `inner.right`, tiga lajur masuk/keluar. `VehicleView` menambahkan `lane`, `target_lane`, dan `changing_to`, dengan koordinat -420–1220. Spawn eksperimen hanya menerima `action`, `expected_run_id`, `direction` dan `kind`; field `distance` lama ditolak. Frontend dan dua layanan Python perlu diperbarui bersama, lalu backend/ATCS direstart. Model kendali Tahap 3/4 tidak berubah.

Setelah mengubah model, jalankan dari root proyek:

```powershell
.\.venv\Scripts\python.exe -m contracts.export_schemas
npm run contracts --prefix frontend
```

Untuk memeriksa tanpa menimpa hasil, gunakan `--check` pada perintah Python dan `npm run contracts:check --prefix frontend`.

## Endpoint baca

| Layanan | GET | Makna |
|---|---|---|
| Backend | `/api/health/live` | Proses hidup, tanpa syarat PostgreSQL |
| Backend | `/api/health` | Kesiapan database/skema; phase_engine not_hosted |
| Backend | `/api/configuration` | Konfigurasi persimpangan tervalidasi |
| Backend | `/api/atcs/health` | Kesehatan ATCS; meneruskan 200/503 yang valid |
| Backend | `/api/atcs/status` | Status operasional ATCS, tanpa timer tambahan |
| Backend | `/api/atcs/events` | Riwayat ATCS beserta cursor |
| Backend | `/api/atcs/traffic` | Kendaraan sintetis dan sinyal dalam satu snapshot |
| Backend | `/api/simulation` | Snapshot ruang percobaan milik akun operator |
| ATCS | `/health/live` | Proses HTTP hidup, terpisah dari mesin fase |
| ATCS | `/health` | Kesiapan proses pengendali dan mesin fase |
| ATCS | `/configuration` | Konfigurasi pengendali |
| ATCS | `/status` | Snapshot mesin fase terakhir |
| ATCS | `/events` | Kejadian sesi yang masih tersimpan |
| ATCS | `/traffic` | Kendaraan sintetis dan sinyal pengendali utama |
| Keduanya | `/docs` | Dokumentasi API lokal |

Seluruh endpoint data backend dalam tabel memerlukan sesi operator, kecuali `/api/health/live` dan dokumentasi `/docs`. Endpoint baca ATCS tetap diagnostik internal localhost; browser menggunakan proxy backend yang terlindungi. Endpoint kendali, heartbeat, observasi dan tanda terima kini tersedia dengan rahasia antarlayanan; bentuk dan validasinya ada pada [protokol Tahap 3/4](control-integration.md). Perintah eksperimen terpisah dijelaskan pada [kontrak 2E/2F](traffic-simulation.md). Respons status ATCS memakai `Cache-Control: no-store`; seluruh respons `/api` backend memakai `private, no-store`.

## Autentikasi dan SessionView

| Metode / endpoint backend | Input / syarat | Hasil |
|---|---|---|
| POST `/api/auth/login` | JSON username/password, Origin yang diizinkan, X-SIGAP-Request: 1 | 200 SessionView dan cookie sesi HttpOnly |
| GET `/api/auth/session` | Cookie sesi valid, akun aktif | 200 SessionView |
| POST `/api/auth/logout` | Cookie sesi, Origin, X-SIGAP-Request: 1, X-CSRF-Token | 204 setelah sesi dicabut dan cookie dihapus |

SessionView memuat `operator`, `expires_at`, `remaining_seconds` (lebih dari 0, maksimal 86.400), serta `csrf_token` 64 karakter heksadesimal. OperatorView memuat `id` UUID, `username`, `display_name`, `role: operator`, dan `permissions: [monitor:read, control:operate]` untuk akun operator saat ini. Tidak ada password, hash password, atau token autentikasi mentah dalam JSON. SessionView ikut diekspor menjadi JSON Schema serta tipe dan validator frontend.

HTTP 401 berarti kredensial/sesi tidak valid atau akun tidak aktif; 403 berarti origin/header/CSRF atau izin tidak sesuai; 422 untuk input tidak sesuai; 429 untuk pembatasan percobaan login; 503 AUTH_UNAVAILABLE ketika penyimpanan akun/sesi tidak dapat digunakan. Respons validasi tidak menggemakan input password. Profil dan token CSRF hanya disimpan dalam memori halaman. Rincian: [Akun operator](operator-auth.md).

## Health

Field: service, stage, liveness, foundation_ready, checked_at, configuration, database, capabilities.

Field stage backend dan ATCS kini `4`; penanda UI Tahap 3/4. Health detail backend memerlukan sesi operator. Bila database/skema gagal saat verifikasi sesi, backend menolak akses dengan 503 AUTH_UNAVAILABLE sebelum membaca laporan health. Liveness backend tetap publik dan terpisah dari kesiapan database. Bila laporan health dapat dibaca, foundation_ready serta database menyatakan kesiapan dan status 503 digunakan jika belum siap. Mesin fase berada di ATCS sehingga kapabilitas backend not_hosted.

ATCS tidak memakai database (not_required). Kesehatan ATCS 200 jika runtime berjalan dan masih memperbarui status. Runtime faulted/stopped/stalled menghasilkan 503; endpoint liveness tetap dapat menjawab 200. Semua merah menunggu konflik adalah keadaan mesin yang berjalan, bukan kerusakan proses.

Kapabilitas fase ATCS: running, faulted, stopped, stalled. Autentikasi akun backend bernilai available/unavailable sesuai kesiapan database/skema; ATCS tidak mengelola login operator. Override bernilai available jika kunci kendali dan layanan siap, atau unavailable; nilai ini menyatakan fasilitas protokol, bukan kesiapan CCTV. AI tetap not_implemented; CCTV not_configured. Kesiapan sumber/perintah yang sebenarnya dibaca melalui ControlStatus.

## AtcsStatus versi 2.0

| Field | Makna |
|---|---|
| schema_version | 2.0; kontrak bertambah dari fondasi 2A |
| intersection_id, operating_context | Simpang dari konfigurasi; konteks simulation |
| run_id | UUID baru setiap startup, identitas sesi pengendali |
| availability | available, unavailable, atau not_implemented |
| engine_state | running/faulted/stopped/stalled; not_started untuk mesin belum dimulai |
| controller, mode | ATCS/SIGAP; fixed_time/adaptive/fallback sesuai otoritas aktual |
| active_approach | U/T/S/B pada hijau/kuning; null pada semua merah |
| phase | green/yellow/all_red; null jika keadaan aktual tidak dapat dipastikan |
| signals | Warna U/T/S/B; hanya pendekat aktif boleh hijau/kuning. Null jika loop stale |
| clearance_state | minimum/waiting_conflict/waiting_command pada semua merah yang berjalan; null di luar itu |
| conflict_area | state clear/occupied/unknown, source assumed_clear/provider, checked_at |
| remaining_seconds | Sisa durasi dari tick ATCS; null saat penahanan konflik atau tidak operasional |
| simulation_time_seconds | Detik monotonic sejak startup, pada tick terakhir |
| sequence_number | Nomor snapshot mesin, naik setiap tick; bukan nomor event |
| updated_at | Timestamp pembaruan mesin terakhir |
| observed_at | Timestamp pembacaan snapshot |
| reason | Alasan keadaan/transisi yang dapat dibaca operator |

Timestamp memiliki zona waktu, UTC pada runtime. Koreksi jam kalender tidak mengubah durasi fase. Browser tidak boleh menghitung fase berikutnya dari waktu sendiri atau menganggap snapshot lama masih berlaku. Bandingkan pasangan run_id dan sequence_number; nomor urut dari sesi berbeda tidak dapat dibandingkan langsung.

Model memvalidasi sinyal agar sesuai fase dan mencegah dua pendekat aktif. Countdown tidak boleh negatif/nonfinite. Saat available, null pada countdown hanya berlaku untuk semua merah yang menunggu konflik. Saat runtime faulted/stopped, model terminalnya semua merah tanpa countdown; ini keadaan simulasi, bukan klaim perangkat lampu fisik menerima perintah.

## Riwayat kejadian

TrafficEvent membawa event_id, run_id, intersection_id, event_type, source, sequence_number, occurred_at, simulation_time_seconds, reason, previous_phase, previous_approach, phase, active_approach.

Jenis yang diterbitkan: service_started, phase_changed, clearance_held, clearance_released, fault, service_stopped, serta control_changed untuk perpindahan kendali. recovered masih disediakan kontrak tanpa penerbit khusus. Nomor event mulai dari 1; event_id menggabungkan sesi dan nomor ini. Riwayat protokol tambahan berada pada ControlStatus.events.

Endpoint events menerima:

- after: hanya kejadian setelah nomor ini; default 0.
- limit: 1–500; default 100.
- run_id: sesi yang diketahui klien; kirim kembali pada pembacaan berikutnya.

Respons TrafficEvents menyertakan events, run_id, oldest_available_sequence, latest_sequence, next_after, has_more, history_truncated, run_changed, generated_at, intersection_id. Gunakan next_after untuk halaman berikutnya, bukan latest_sequence jika has_more masih true.

Jika sesi berubah, server mengabaikan cursor lama dan mengirim halaman awal sesi baru dengan run_changed true. Cursor tertinggal akibat retensi menghasilkan history_truncated true. Cursor di depan riwayat pada sesi yang sama menghasilkan HTTP 400 CURSOR_AHEAD; parameter di luar rentang menghasilkan 422. Riwayat berupa buffer memori 1.000 kejadian, tidak persisten dan hilang saat proses berakhir.

Backend memvalidasi kontrak, identitas layanan/simpang, serta keselarasan sesi event. Kegagalan koneksi atau respons rusak menghasilkan 503 ATCS_UNAVAILABLE. Laporan 503 valid dari ATCS diteruskan agar gangguan mesin dapat dibedakan dari API tidak terjangkau.
