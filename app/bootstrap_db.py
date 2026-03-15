import time

from app import create_app
from app.base_model import db


def bootstrap_db(retries: int = 30, delay_seconds: int = 2) -> None:
    app = create_app()
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            with app.app_context():
                with db.engine.begin() as connection:
                    connection.exec_driver_sql('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
                db.create_all()
            return
        except Exception as exc:
            last_error = exc
            if attempt == retries - 1:
                break
            print(f"database bootstrap attempt {attempt + 1}/{retries} failed: {exc}")
            time.sleep(delay_seconds)

    assert last_error is not None
    raise last_error


if __name__ == "__main__":
    bootstrap_db()
