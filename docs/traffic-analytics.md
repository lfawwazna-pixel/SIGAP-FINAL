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

## Perbandingan ATCS–SIGAP

Tombol **Jalankan perbandingan setara** membuat satu jadwal kedatangan Poisson dan pilihan belok dari seed. Kedua kendali memakai **jadwal yang persis sama**, durasi uji, antrean awal kosong, headway pelayanan, kuning, semua-merah, dan keluaran diasumsikan lancar. Hash jadwal disimpan agar pengulangan dapat diperiksa. Eksperimen terpisah dari aplikasi/ATCS; tidak mengirim perintah lampu atau mengaktifkan GPU.

Model FIFO per pendekat/pergerakan berjalan per 1 detik, dengan hasil tiap 15 detik. Belok kiri memakai ruas pintas yang diasumsikan lancar. ATCS memakai waktu dasar di konfigurasi simpang. SIGAP memakai implementasi `AdaptivePolicy` dan konfigurasi kebijakan proyek, dengan batas hijau video 180 detik serta perlindungan pandangan sebagian dan penurunan bertahap. Parameter kebijakan, baseline, dan transisi ikut disimpan dalam laporan/CSV.

Fraksi deteksi hanya mengurangi hitungan yang diberikan ke kebijakan; waktu tunggu tertua diasumsikan diketahui dari model. Ini keterbatasan penting, bukan estimasi recall model YOLO sebenarnya. Gerakan ruang, output terblokir, kalibrasi kamera, kelas armada, dan occlusion dinamis belum dimodelkan. Ubah seed/arus/durasi/cakupan untuk menilai sensitivitas. Hasil dapat lebih baik, sama, atau lebih buruk; tidak ada persentase penghematan yang dipaksakan. Baseline observasi 6–7 menit dari rencana belum menjadi data validasi eksperimen ini.

Indikator:

| Faktor | Perhitungan dan batasnya |
| --- | --- |
| Waktu tunggu | Akumulasi vehicle-seconds antrean / semua kedatangan, termasuk yang belum terlayani; menghindari bias hanya kendaraan yang selesai. |
| Antrean | Kendaraan yang masih mengantre, gabungan empat pendekat. |
| Panjang antrean | Total kendaraan antre × asumsi jarak/veh; bukan panjang satu lajur atau meter kalibrasi video. |
| BBM idle | Vehicle-seconds / 3600 × liter per kendaraan per jam. Tidak mencakup akselerasi/perjalanan. |
| CO₂ | Estimasi BBM idle × faktor kg/L; default setara bensin, bukan seluruh campuran armada. |
| Biaya BBM | Estimasi idle × harga asumsi, bukan harga pasar saat ini. |
| Biaya waktu | Vehicle-seconds / 3600 × nilai waktu per kendaraan per jam. |
| Pelayanan | Kendaraan kumulatif keluar antrean pada jendela uji; belum menjadi throughput lapangan. |
| Darurat/keselamatan | Belum dievaluasi; perlu klip terverifikasi dan pengujian EVP/transisi tersendiri. |

Asumsi default dapat diedit: idle 0,8 L/jam/veh; CO₂ 2,35 kg/L; BBM Rp10.000/L; nilai waktu Rp20.000/veh/jam; jarak 6,5 m/veh. Semua merupakan **asumsi**, bukan angka hasil pengukuran. Faktor CO₂ dibulatkan dari [EPA: 8.887 gram per US gallon bensin](https://www.epa.gov/greenvehicles/greenhouse-gas-emissions-typical-passenger-vehicle) / 3,785411784 L ≈2,35 kg/L. Idle armada, harga, dan nilai waktu harus diganti dengan sumber lokal sebelum dipakai untuk klaim evaluasi.

## Endpoint dan validasi

- `GET /api/analytics`: pengamatan cache, kualitas, prediksi, laporan terakhir; login wajib.
- `POST /api/analytics/comparison`: input terbatasi; login, izin `control:operate`, Origin terpercaya, `X-SIGAP-Request`, dan CSRF wajib.
- `GET /api/analytics/comparison/{id}/csv`: metadata/parameter/hash dan kedua deret; login wajib.

Pengujian mencakup parsing/proyeksi ruas, nilai invalid, cache/restart, key tidak bocor, rate limit, holdout tanpa data masa depan, forecast ditahan, kedatangan sama/konservasi kendaraan, rumus faktor, nol kendaraan, autentikasi/CSRF/CSV, dua garis, pergantian indikator, regresi hasil, dan rute login. Pengujian tidak menjadi validasi akurasi lapangan, respons darurat, atau manfaat nyata SIGAP.
