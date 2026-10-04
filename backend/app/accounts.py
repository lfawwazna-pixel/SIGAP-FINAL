"""Explicit local account provisioning: python -m backend.app.accounts --help."""
import argparse
import getpass
import warnings

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.auth import PASSWORD_HASHER, normalize_username, validate_password
from backend.app.database import check_database, make_engine
from backend.app.models import OperatorAccount, OperatorSession
from backend.app.settings import Settings


def create_operator(db: Session, username: str, display_name: str, password: str, *, allow_short=False):
    username = normalize_username(username)
    display_name = display_name.strip()
    if not 1 <= len(display_name) <= 120 or any(ord(char) < 32 for char in display_name):
        raise ValueError("Nama tampilan harus 1–120 karakter tanpa karakter kontrol.")
    validate_password(password, allow_short=allow_short)
    if db.scalar(select(OperatorAccount.id).where(func.lower(OperatorAccount.username) == username)):
        raise ValueError("Nama pengguna sudah dipakai; akun yang ada tidak diubah.")
    account = OperatorAccount(username=username, display_name=display_name,
                              password_hash=PASSWORD_HASHER.hash(password), is_active=True)
    db.add(account)
    db.flush()
    return account


def read_password():
    # Never silently fall back to echoing a password in a non-interactive terminal.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass("Kata sandi baru: ")
        if password != getpass.getpass("Ulangi kata sandi: "):
            raise ValueError("Kedua kata sandi berbeda.")
    return password


def main():
    parser = argparse.ArgumentParser(description="Kelola akun operator SIGAP secara lokal; tidak ada akun bawaan.")
    parser.add_argument("action", choices=["create", "disable", "enable", "reset-password"])
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name")
    parser.add_argument("--allow-short-password", action="store_true", help="Pilihan eksplisit untuk prototipe lokal; mengizinkan sandi di bawah 15 karakter.")
    args = parser.parse_args()
    engine = make_engine(Settings())
    try:
        report = check_database(engine)
        if report.status != "reachable" or report.schema_status != "current":
            raise ValueError("Database belum siap. Isi konfigurasi koneksi dan jalankan migrasi sampai head.")
        username = normalize_username(args.username)
        if args.action == "create" and not args.display_name:
            raise ValueError("--display-name diperlukan saat membuat akun.")
        password = read_password() if args.action in ("create", "reset-password") else None
        with Session(engine) as db, db.begin():
            if args.action == "create":
                create_operator(db, username, args.display_name, password, allow_short=args.allow_short_password)
            else:
                account = db.scalar(select(OperatorAccount).where(func.lower(OperatorAccount.username) == username).with_for_update())
                if account is None:
                    raise ValueError("Akun tidak ditemukan.")
                if args.action == "reset-password":
                    validate_password(password, allow_short=args.allow_short_password)
                    account.password_hash = PASSWORD_HASHER.hash(password)
                else:
                    account.is_active = args.action == "enable"
                db.execute(delete(OperatorSession).where(OperatorSession.operator_id == account.id))
        print(f"Berhasil: {args.action} untuk operator {username}.")
    except (ValueError, getpass.GetPassWarning) as exc:
        raise SystemExit(str(exc)) from None
    except IntegrityError:
        raise SystemExit("Nama pengguna sudah dipakai; perubahan dibatalkan.") from None
    except SQLAlchemyError:
        raise SystemExit("Database tidak tersedia; perubahan dibatalkan.") from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
