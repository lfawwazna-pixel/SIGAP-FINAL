# Analitik wilayah dan dampak SIGAP

Halaman `/analytics` tersedia melalui **Analitik & dampak** pada monitor. Login operator tetap diperlukan. Grafik dapat diperiksa dengan pointer, penggeser keyboard, atau tabel data. Modul halaman dimuat saat dibuka; tidak menambah proses GPU. Aplikasi tetap memakai model/video yang telah terpasang.

## Sumber wilayah

Backend mengambil Traffic Flow TomTom untuk empat titik dalam `configs/traffic-analytics.json`. Titik pusat simpang ditemukan melalui hasil CrossStreet TomTom untuk Jalan Ibrahim Adjie & Jalan Soekarno Hatta, Bandung: -6.945316, 107.641841. Titik pengamatan pendekat sekitar 150–190 meter dari pusat merupakan penempatan awal. Polyline hasil provider diperiksa dengan proyeksi jarak terdekat. Ruas hasil dapat mencakup flyover atau ruas yang bukan lajur lampu; penamaan U/T/S/B tidak membuktikan kesamaan lajur CCTV. UI memperlihatkan titik, jarak ruas, keyakinan, dan waktu pengambilan sampel.

Indeks kemacetan = `clamp(100 × (1 − currentSpeed/freeFlowSpeed), 0, 100)`. Angka ini **bukan kepadatan kendaraan/km**, jumlah kendaraan, panjang antrean kamera, atau waktu menunggu lampu. Tambahan waktu ruas adalah selisih waktu perjalanan ruas dan acuan lancar. Rata-rata wilayah memakai ruas mutakhir dengan keyakinan >=0,5, tidak ditutup, dan hasil proyeksi <=250 meter. Sampel >10 menit, waktu masa depan, penutupan, keyakinan rendah, dan kegagalan provider diberi status khusus.

TomTom adalah kondisi wilayah saat pengambilan data; CCTV rekaman dapat berasal dari tanggal/waktu berbeda. Data wilayah tidak masuk ke keputusan lampu, dan tidak menjadi bukti dampak SIGAP.

Referensi primer: [Flow Segment Data TomTom](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data), [cakupan pasar](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/product-information/market-coverage).

## Konfigurasi dan penyimpanan

Isi pada `.env` backend, dengan key yang memiliki akses Traffic API:

```dotenv
SIGAP_TOMTOM_API_KEY=isi_key_lokal
SIGAP_TOMTOM_POLL_SECONDS=120
```

Key lokal telah dipasang saat pengerjaan, tanpa dimasukkan ke kode/frontend/Git. Jangan menaruh key pada variabel `VITE_`. Tidak ada key dalam respons API, ekspor CSV, atau pesan kegagalan. Tidak ada perubahan akun atau paket TomTom. Backend menjalankan empat permintaan per interval, bukan per pengunjung atau refresh halaman. Default 120 detik (~120 permintaan/jam); pilihan dibatasi 60–300 detik. HTTP 429 menahan pengambilan berikutnya sekurangnya 10 menit. Kuota akun tetap berlaku.

Cache SQLite `work/analytics/traffic.sqlite3` menyimpan pengamatan yang benar-benar diterima; tidak mengisi waktu kosong. Retensi lokal pengamatan 72 jam dan maksimal 50 laporan perbandingan. Respons grafik menyediakan 180 sampel terakhir per ruas. Compose memakai volume `sigap_analytics`; akses key tetap pada backend. Penyimpanan gagal tidak menghentikan pengendali. Bila key kosong, halaman menampilkan status belum dikonfigurasi dan perbandingan simulasi tetap tersedia.

## Prediksi jangka pendek

Model autoregresif AR(2) ridge lokal belajar dari indeks kemacetan, tanpa GPU/API AI tambahan. Minimal **12 sampel berurutan** yang valid, interval 30–360 detik; pada interval 120 detik memerlukan sekitar 22–24 menit sejak pengambilan pertama. Maksimal 90 sampel digunakan. Pemadaman, jeda panjang, penutupan, atau sampel tidak valid memutus rangkaian. Tidak dibuat riwayat atau prediksi saat data belum cukup.

Bagian akhir riwayat menjadi holdout kronologis. Model dilatih hanya pada bagian lebih awal untuk pengujian satu langkah, dibandingkan dengan nilai terakhir/persistence. Bila tidak mengungguli baseline dengan toleransi 5%, forecast memakai persistence dan UI menjelaskannya. Koefisien kemudian dilatih ulang dari riwayat tersedia untuk proyeksi rekursif sampai 30 menit. UI memperlihatkan metode, jumlah sampel, dan galat MAE dalam poin persentase.

Area prediksi adalah rentang heuristik dari galat yang melebar seiring horizon, **bukan interval keyakinan 95%**. Model statistik ini belum tervalidasi lapangan dan belum mengandung pola harian, cuaca, acara, atau insiden. Sampel kedaluwarsa/tidak layak dan error pengambilan menahan prediksi.

## Perbandingan ATCS–SIGAP · queue-v2

Eksperimen ini **terpisah dari kendali operasional**. Tombol tidak mengaktifkan SIGAP, mengirim perintah lampu atau menjalankan GPU. Tracking, zona, map ATCS dan simulasi kendaraan tidak diubah. Grafik TomTom tetap konteks ruas pada waktu pengambilan, bukan masukan jumlah kendaraan atau bukti manfaat kendali.

### Masukan zona dan skenario manual

Panel **Gunakan pengamatan zona** memerlukan keempat kamera berjalan, kalibrasi tidak ambigu dan tracking mutakhir berkelanjutan minimal 60 detik. Jendela maksimum 180 detik; jeda lebih dari 3 detik memulai jendela baru. Gunakan titik bawah-tengah bounding box dan aturan admission zona yang sama dengan dashboard. Satu ID baru yang teramati sebelum garis henti dihitung sekali; kendaraan kiri bebas berasal dari zona outer. Kendaraan pada frame awal setiap tracker session tidak dianggap kedatangan baru. ID coasted, kendaraan di luar zona, yang sudah melewati garis henti terkontrol, dan EVP dikecualikan. Rekaman looping ditandai dan populasi frame pertama loop tidak dihitung sebagai kedatangan.

Laju per arah = identitas biasa baru / detik pengamatan × 60. Campuran kelas dan belokan mengikuti zona outer/middle/inner, bukan tujuan perjalanan yang telah diverifikasi lapangan. Backend membekukan fingerprint profil dan memverifikasi sumber serta kalibrasi; token berlaku maksimal 10 menit. Backend mengganti angka laju/kelas/belokan dari klien dengan profil tersimpan. Profil kosong yang valid menghasilkan nol, bukan arus default. Laju >180 kendaraan/menit ditolak sebagai di luar batas model, tidak dipotong diam-diam.

Profil adalah **kedatangan teramati dalam zona**, bukan arus sebenarnya: ID switch, occlusion, kendaraan sudah berada di zona saat frame awal, dan pemotongan arus oleh ROI dapat menimbulkan bias. Rekaman berulang bukan sampel lapangan independen. Belum cukup untuk klaim akurasi arus. Skenario manual tetap tersedia tanpa tracking/TomTom; preset ringan merata, tidak seimbang dan padat adalah asumsi uji yang dapat diedit. Tidak ada preset yang dijamin memberi keuntungan.

### Rancangan berpasangan

Default 10 pasangan seed berturut-turut (rentang 5–30), warmup 300 detik (0–900), pengamatan 900 detik (300–1800). Jadwal Poisson mencakup warmup + pengamatan. Setiap pasangan memakai **identitas, waktu kedatangan, kelas, asal, belokan dan observation mark yang identik**. Hash jadwal aktual disimpan per seed; fraksi deteksi tidak mengubah kendaraan sebenarnya. Ulangan tidak dipilih berdasarkan hasil. Kendaraan awal setiap strategi setelah warmup bisa berbeda karena kebijakan berbeda; kedatangan selama warmup tetap sama. Jumlah peserta dan antrean awal kedua strategi dilaporkan agar perbedaan ini terbuka.

ATCS baseline memakai hijau U/T/S/B **85/150/95/100 detik**, kuning 3, semua merah 2 dari **Tabel 7 penelitian Polban (2025)**. Urutan U–T–S–B adalah desain proyek. Studi memakai data Dishub 2023 yang diproyeksikan; konfigurasi ATCS terkini belum dikonfirmasi. Baseline ini bukan pembuktian bahwa semua ATCS memakai waktu tetap. Sumber: [penelitian simpang yang sama](https://jurnal.polban.ac.id/proceeding/article/view/6701/4025).

SIGAP menjalankan `AdaptivePolicy` yang dipakai aplikasi, baseline yang sama, maksimum hijau dari pengaturan ATCS lokal (default 180 detik), serta guard video/pandangan sebagian dan penurunan bertahap. Tidak ada algoritme khusus analitik untuk membuat SIGAP menang. Fraksi deteksi default 1 berarti seluruh identitas **skenario** terlihat; ini bukan klaim recall YOLO 100%. Jika sensitivitas diturunkan, identitas tak terlihat tidak menyumbang count atau waktu tunggu tertua. Cakupan penuh/sebagian terpisah dari fraksi deteksi; default sebagian.

### Waktu, pelayanan dan ruang

Mesin antrean memakai **kejadian dengan waktu pecahan tepat**, bukan pembulatan per detik. Integral antrean memakai keadaan sebelum event, termasuk sebelum keberangkatan. Startup default 2 detik dan headway mobil 2,2 detik adalah asumsi yang dapat dikalibrasi, mengacu konsep [FHWA Signal Timing Manual, Chapter 3](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter3.htm). Model bukan simulasi mikro seluruh gerak peta.

Satu antrean FIFO per pergerakan/arah. Motor berturut-turut berbagi hingga 3 posisi dalam satu baris, tanpa melewati mobil. Bus/truk default ruang dan headway 2× mobil. Ruang baris mobil default 6,5 m, motor 3 m. Angka ini asumsi, bukan ukuran terkalibrasi di video. Kiri bebas diasumsikan keluar setelah headway tanpa konflik. Model belum memperhitungkan percepatan, konflik geometris, kapasitas keluaran jaringan, spillback, perubahan lajur atau EVP; pergantian lampu tetap melalui kuning dan semua merah.

### Rumus dan interpretasi

| Indikator | Rumus / makna |
| --- | --- |
| Vehicle-seconds `W` | Integral jumlah kendaraan dalam antrean terhadap waktu, terpisah per kelas dan arah. Waktu sebelum warmup dikecualikan. |
| Peserta `N` | Antrean awal + kedatangan dalam jendela pengamatan. |
| Tunggu rata-rata terbatas | `W/N`; 0 jika N=0. Kendaraan belum selesai ikut. Ini bukan waktu tunggu penuh hingga semua kendaraan selesai, dan bukan seluruh control delay HCM (yang juga mencakup akselerasi/deselerasi). |
| Tunggu kendaraan selesai | Waktu terakumulasi dalam jendela per kendaraan yang selesai; tersedia pada hasil mentah, tidak menjadi kartu utama karena bias terhadap peserta yang cepat terlayani. |
| Konservasi | `antrean + terlayani = antrean awal + kedatangan`, pada setiap sampel dan ulangan. |
| Panjang antrean | Σ ruang baris dari semua lajur; motor dalam satu baris tidak menambah panjang sebanyak jumlah motor. Maksimum panjang satu lajur dilaporkan terpisah. Tidak dibatasi panjang map dan bukan ukuran kamera. |
| BBM | Σ `(W_k/3600 × idle_k L/jam)`; hanya antrean/idle. |
| CO₂ | Σ `liter_k × faktor bahan bakar_k`. |
| Biaya BBM | Σ `liter_k × harga bahan bakar_k`. |
| Biaya waktu | `W/3600 × nilai waktu per kendaraan-jam`; tidak mengasumsikan jumlah penumpang. |
| Biaya total | Biaya BBM + biaya waktu; biaya non-idle tidak dihitung. |

Referensi idle [DOE AFDC PREP, Table 5](https://afdc.energy.gov/prep/prep_methodology.html): mobil bensin 0,23 US gal/jam ≈0,871 L/jam; kendaraan diesel berat 0,8 US gal/jam ≈3,028 L/jam. Pemakaian nilai kendaraan berat untuk bus/truk adalah asumsi. Motor default 0,2 L/jam adalah asumsi proyek tanpa kalibrasi lokal. Profil tiap kelas (ruang, headway, idle, bahan bakar, motor sejajar) dapat diedit. Faktor CO₂ dibulatkan dari [EPA](https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator-calculations-and-references) menjadi 2,35 kg/L bensin dan 2,69 kg/L diesel. YOLO tidak mengidentifikasi bahan bakar; pemetaan kelas ke bahan bakar juga asumsi. Harga bensin/diesel default Rp10.000/L dan nilai waktu Rp20.000/kendaraan-jam adalah asumsi eksperimen, bukan harga terkini. Semua faktor disimpan dalam laporan/CSV.

Kartu memakai **rata-rata seluruh ulangan**. Grafik memperlihatkan pasangan **seed pertama**, berlabel demikian; bukan rata-rata seluruh seed. Tabel per arah menunjukkan tunggu, terlayani, tersisa dan peserta, agar perburukan pada arah tertentu tidak tersembunyi. Tidak ada persen jika baseline nol.

Untuk setiap indikator, `d_i = ATCS_i − SIGAP_i`; untuk pelayanan, arah dibalik (`SIGAP_i − ATCS_i`). Interval berpasangan 95% = `mean(d) ± t_(n−1, 0,975) × s_d/√n`. Persen = `mean(d)/mean(ATCS) × 100`; bukan rata-rata persentase. Interval positif = lebih baik pada skenario ini, negatif = lebih buruk, melintasi nol = belum konsisten antarulangan, semua nol = sama. Interval hanya variasi seed skenario, **bukan ketidakpastian keseluruhan model atau manfaat lapangan**. Prinsip evaluasi kondisi setara dan ketergantungan terhadap baseline: [FHWA Evaluating Adaptive Signal Control, Chapter 3](https://ops.fhwa.dot.gov/publications/fhwahop13031/chap3.htm).

Arsip metode lama tetap dapat dibaca dengan label “metode sebelumnya”; tidak diubah seolah memakai armada campuran atau banyak ulangan. Jalankan ulang untuk mendapat queue-v2. Ekspor menyertakan metode, input lengkap, provenance profil, sumber, asumsi, konfigurasi, hash, seluruh hasil akhir ulangan, ringkasan interval dan grafik seed pertama. Hasil keselamatan/respons EVP tetap `not_evaluated` pada eksperimen dampak ini.

## Endpoint dan validasi

- `GET /api/analytics`: pengamatan cache, kualitas, prediksi, profil zona, laporan terakhir; login wajib.
- `POST /api/analytics/comparison`: input terbatasi; login, izin `control:operate`, Origin terpercaya, `X-SIGAP-Request`, dan CSRF wajib.
- `GET /api/analytics/comparison/{id}/csv`: metadata/parameter/hash dan kedua deret; login wajib.

Pengujian mencakup parsing/proyeksi ruas, nilai invalid, cache/restart, key tidak bocor, rate limit, holdout tanpa data masa depan, forecast ditahan, kedatangan sama/konservasi kendaraan, rumus faktor, nol kendaraan, autentikasi/CSRF/CSV, dua garis, pergantian indikator, regresi hasil, dan rute login. Pengujian tidak menjadi validasi akurasi lapangan, respons darurat, atau manfaat nyata SIGAP.
