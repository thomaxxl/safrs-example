from __future__ import annotations

from verify_target import run_target


if __name__ == "__main__":
    raise SystemExit(
        run_target(
            "nw-flask",
            "nw_flask_app.py",
            target_env={"SAFRS_NW_RESET_DB": "1"},
            collection_id_keys={"Customer": "CustomerId", "Employee": "EmployeeId", "Order": "OrderId"},
        )
    )
