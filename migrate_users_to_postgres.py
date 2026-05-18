"""Copy existing AIRAS users from a local SQLite database into PostgreSQL.

Use this when you already have accounts in `data/app.db` locally and want
the same people to be able to log in on Render's PostgreSQL database.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from sqlalchemy import Boolean, Column, Float, Integer, String, create_engine, select
from sqlalchemy.orm import declarative_base, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_SQLITE = BASE_DIR / "data" / "app.db"

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)
    password_hash = Column("password", String(255), nullable=False)
    salt = Column(String(64), nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(String(32), nullable=False)


class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    uploaded_at = Column(String(32), nullable=False)
    filename = Column(String(255), nullable=False)
    sheet_name = Column(String(255), nullable=True)
    total_students = Column(Integer, nullable=True)
    passed = Column(Integer, nullable=True)
    failed = Column(Integer, nullable=True)
    pass_percent = Column(Float, nullable=True)
    average_sgpa = Column(Float, nullable=True)
    institution = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    class_name = Column(String(255), nullable=True)
    semester = Column(String(64), nullable=True)
    academic_year = Column(String(64), nullable=True)
    file_hash = Column(String(64), nullable=True)


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def normalize_database_url(raw_url: str) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        raise ValueError("A target database URL is required.")
    if raw_url.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw_url[len("postgres://") :]
    if raw_url.startswith("postgresql://") and "+psycopg" not in raw_url:
        return "postgresql+psycopg2://" + raw_url[len("postgresql://") :]
    return raw_url


def build_target_engine(target_url: str):
    engine_kwargs = {"future": True, "pool_pre_ping": True}
    if target_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(target_url, **engine_kwargs)


def read_source_users(sqlite_path: Path):
    if not sqlite_path.exists():
        raise FileNotFoundError(f"Source SQLite database not found: {sqlite_path}")

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        columns = {row[1] for row in cur.execute("PRAGMA table_info(users)").fetchall()}
        if not columns:
            raise RuntimeError("The source database does not contain a users table.")

        email_column = "email" if "email" in columns else "username"
        password_column = "password" if "password" in columns else "password_hash"
        if email_column not in columns or password_column not in columns:
            raise RuntimeError("The source users table does not have the expected email/password columns.")

        select_columns = [
            "id",
            email_column,
            "name",
            "department",
            password_column,
            "salt",
            "is_admin",
            "created_at",
        ]
        query = f"SELECT {', '.join(select_columns)} FROM users"
        rows = cur.execute(query).fetchall()

        users = []
        email_by_source_id = {}
        for row in rows:
            email = normalize_email(row[email_column])
            if not email:
                continue
            source_id = int(row["id"]) if row["id"] is not None else None
            email_by_source_id[source_id] = email
            users.append(
                {
                    "source_id": source_id,
                    "email": email,
                    "name": (row["name"] or "").strip(),
                    "department": (row["department"] or "").strip() or None,
                    "password_hash": row[password_column],
                    "salt": (row["salt"] or None),
                    "is_admin": bool(row["is_admin"]),
                    "created_at": row["created_at"] or "",
                }
            )
        return users, email_by_source_id
    finally:
        conn.close()


def read_source_history(sqlite_path: Path):
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "history" not in tables:
            return []
        rows = cur.execute(
            """
            SELECT id, user_id, uploaded_at, filename, sheet_name, total_students, passed, failed,
                   pass_percent, average_sgpa, institution, department, class_name, semester,
                   academic_year, file_hash
            FROM history
            """
        ).fetchall()
        history = []
        for row in rows:
            history.append(dict(row))
        return history
    finally:
        conn.close()


def upsert_users(target_session, users):
    inserted = 0
    updated = 0
    target_users = {}

    for item in users:
        email = item["email"]
        user = target_session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                name=item["name"],
                department=item["department"],
                password_hash=item["password_hash"],
                salt=item["salt"],
                is_admin=item["is_admin"],
                created_at=item["created_at"],
            )
            target_session.add(user)
            inserted += 1
        else:
            changed = False
            for field in ("name", "department", "password_hash", "salt", "is_admin", "created_at"):
                new_value = item[field]
                if getattr(user, field) != new_value:
                    setattr(user, field, new_value)
                    changed = True
            if changed:
                updated += 1
        target_session.flush()
        target_users[email] = user

    target_session.commit()
    return inserted, updated, target_users


def upsert_history(target_session, history_rows, source_email_by_id, target_users_by_email):
    inserted = 0
    for row in history_rows:
        source_user_id = row.get("user_id")
        source_email = source_email_by_id.get(source_user_id)
        if not source_email:
            continue
        target_user = target_users_by_email.get(source_email)
        if target_user is None:
            continue

        duplicate = target_session.scalar(
            select(History.id).where(
                History.user_id == target_user.id,
                History.uploaded_at == row["uploaded_at"],
                History.filename == row["filename"],
                History.sheet_name == row["sheet_name"],
                History.file_hash == row["file_hash"],
            )
        )
        if duplicate is not None:
            continue

        target_session.add(
            History(
                user_id=target_user.id,
                uploaded_at=row["uploaded_at"],
                filename=row["filename"],
                sheet_name=row["sheet_name"],
                total_students=row["total_students"],
                passed=row["passed"],
                failed=row["failed"],
                pass_percent=row["pass_percent"],
                average_sgpa=row["average_sgpa"],
                institution=row["institution"],
                department=row["department"],
                class_name=row["class_name"],
                semester=row["semester"],
                academic_year=row["academic_year"],
                file_hash=row["file_hash"],
            )
        )
        inserted += 1

    target_session.commit()
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate AIRAS users from SQLite to PostgreSQL.")
    parser.add_argument(
        "--source",
        default=os.environ.get("AIRAS_SOURCE_SQLITE", str(DEFAULT_SOURCE_SQLITE)),
        help="Path to the source SQLite database file.",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("DATABASE_URL") or os.environ.get("AIRAS_DATABASE_URL"),
        help="Target database URL. Usually your Render PostgreSQL DATABASE_URL.",
    )
    parser.add_argument(
        "--include-history",
        action="store_true",
        help="Also copy history rows for any users that were migrated.",
    )
    args = parser.parse_args()

    source_path = Path(args.source).expanduser().resolve()
    target_url = normalize_database_url(args.target)
    target_engine = build_target_engine(target_url)
    TargetSession = sessionmaker(bind=target_engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)

    Base.metadata.create_all(bind=target_engine)

    users, source_email_by_id = read_source_users(source_path)
    if not users:
        print("No users found in the source database.")
        return 0

    with TargetSession() as session:
        inserted, updated, target_users_by_email = upsert_users(session, users)
        print(f"Users migrated: inserted={inserted}, updated={updated}, total={len(users)}")

        if args.include_history:
            history_rows = read_source_history(source_path)
            history_inserted = upsert_history(session, history_rows, source_email_by_id, target_users_by_email)
            print(f"History migrated: inserted={history_inserted}")

    print("Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
