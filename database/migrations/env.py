from alembic import context

from backend.app.database import make_engine
from backend.app.models import Base
from backend.app.settings import Settings

settings = Settings()
url = settings.database_url()
if url is None:
    raise RuntimeError("POSTGRES_PASSWORD belum diisi. Siapkan .env terlebih dahulu.")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(settings)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
