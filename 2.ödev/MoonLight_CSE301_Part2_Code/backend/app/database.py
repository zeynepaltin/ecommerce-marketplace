"""CSE 301 Database Management - Fall 2026 - Project Part 2
Multi-Vendor E-Commerce Marketplace - Group: Moon Light

Group members (Name Surname - Student Number):
  Mehmet Çolaker - 220610028, Emre Sefa Kazan - 230610019,
  Ahmet Yasin Akyüz - 230610015, Hüseyin Gürses - 230610029,
  Zeynep Sümeyra Altın - 230610005, Ulaş Budak - 25060902060

Database access layer. The application never sends ad-hoc SQL: every
operation is a call of a stored procedure (CALL sp_name(...)).
"""
import re

import pymysql
import pymysql.cursors

from .config import settings

_PROC_NAME = re.compile(r"^sp_[a-z_]+$")


class DatabaseError(Exception):
    """Error raised by a stored procedure, with a message that can be shown to the user."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


class Database:
    """One MySQL connection per HTTP request; wraps stored-procedure calls."""

    def __init__(self):
        self._conn = pymysql.connect(
            host=settings.db_host, port=settings.db_port, user=settings.db_user,
            password=settings.db_password, database=settings.db_name, charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor, autocommit=True,
        )

    def call(self, procedure: str, *args) -> list[dict]:
        """Run CALL procedure(args) in a single round trip and return the first result set."""
        if not _PROC_NAME.match(procedure):
            raise ValueError(f"Invalid procedure name: {procedure}")
        placeholders = ", ".join(["%s"] * len(args))
        try:
            with self._conn.cursor() as cur:
                cur.execute(f"CALL {procedure}({placeholders})", args)
                rows = list(cur.fetchall())
                while cur.nextset():  # consume the status result of CALL
                    pass
                return rows
        except pymysql.err.MySQLError as exc:
            code = exc.args[0] if exc.args else None
            text = exc.args[1] if len(exc.args) > 1 else str(exc)
            if code == 1644:            # SIGNAL SQLSTATE '45000' from a procedure or trigger
                raise DatabaseError(text, code) from exc
            if code == 3819:            # CHECK constraint violated
                raise DatabaseError("One of the entered values is not allowed.", code) from exc
            if code in (1452, 1451):    # foreign key violation
                raise DatabaseError("The referenced record does not exist or is still in use.", code) from exc
            raise DatabaseError("A database error occurred. Please try again.", code) from exc

    def one(self, procedure: str, *args) -> dict | None:
        rows = self.call(procedure, *args)
        return rows[0] if rows else None

    def close(self):
        self._conn.close()


def get_db():
    """FastAPI dependency: opens a connection for the request and always closes it."""
    db = Database()
    try:
        yield db
    finally:
        db.close()
