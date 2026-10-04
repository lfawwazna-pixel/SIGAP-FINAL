# Dependency yang dipilih

Versi langsung dipilih dari rilis stabil dan diverifikasi terhadap registry pada 3 Oktober 2026. Daftar ini mencatat pilihan proyek; tidak mengklaim setiap paket harus merupakan rilis mayor terbaru. Lockfile menyimpan dependency transitif dan hash; pemasangan ulang memakai `uv sync --locked` dan `npm ci`.

| Komponen | Versi |
|---|---|
| Python | 3.14.x; diuji lokal 3.14.7 |
| uv | 0.11.15 |
| FastAPI | 0.142.2 |
| Uvicorn | 0.54.0 |
| Pydantic / pydantic-settings | 2.13.5 / 2.15.0 |
| SQLAlchemy / Alembic | 2.1.2 / 1.20.0 |
| psycopg binary | 3.3.6 |
| argon2-cffi | 25.1.0 |
| httpx / pytest | 0.28.1 / 9.1.1 |
| PostgreSQL image | 17.11-bookworm |
| Node | 24 LTS untuk container; diuji lokal 26.10.0 |
| React / React DOM | 19.2.8 |
| TypeScript | 5.9.3 |
| Vite / React plugin | 7.3.6 / 5.2.0 |
| Vitest / jsdom | 3.2.7 / 26.1.0 |
| Testing Library React | 16.3.3 |
| Ajv / ajv-formats | 8.20.0 / 3.0.1 |
| json-schema-to-typescript | 16.0.0 |
| IBM Plex Sans / Mono | 5.3.0 |

Sumber paket adalah [npm Registry](https://registry.npmjs.org/) dan [PyPI](https://pypi.org/). Acuan kompatibilitas: [Vite](https://vite.dev/guide/), [rilis FastAPI](https://fastapi.tiangolo.com/release-notes/), [versi PostgreSQL yang didukung](https://www.postgresql.org/support/versioning/). PostgreSQL 17 tetap dipilih sebagai rilis yang didukung; image 17.11-bookworm telah dijalankan melalui Compose dan diuji dengan migrasi serta autentikasi nyata pada Tahap 2D.

Lockfile aplikasi tidak mengunci base image Docker ke digest. Tag Python/Node dengan versi mayor tetap menerima patch. Penguncian digest dan hardening image menjadi pekerjaan saat persiapan deployment; tidak ada deployment pada tahap ini.

Pengujian Python saat ini menampilkan peringatan deprecation dari Starlette TestClient karena memakai httpx. Semua tes terkait tetap berhasil. Migrasi test transport ke httpx2 dapat dilakukan saat pembaruan dependency berikutnya; peringatan tidak disembunyikan.
