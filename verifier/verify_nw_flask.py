from __future__ import annotations

from verify_target import run_target


if __name__ == "__main__":
    raise SystemExit(
        run_target(
            "nw-flask",
            "nw_flask_app.py",
            target_env={"SAFRS_NW_RESET_DB": "1"},
            collection_id_keys={
                "Category": "CategoryId",
                "Customer": "CustomerId",
                "CustomerDemographic": "CustomerDemographicId",
                "Department": "DepartmentId",
                "Employee": "EmployeeId",
                "EmployeeAudit": "EmployeeAuditId",
                "EmployeeTerritory": "EmployeeTerritoryId",
                "Location": "LocationId",
                "Order": "OrderId",
                "OrderDetail": "OrderDetailId",
                "Product": "ProductId",
                "Region": "RegionId",
                "SampleDBVersion": "SampleDBVersionId",
                "Shipper": "ShipperId",
                "Supplier": "SupplierId",
                "Territory": "TerritoryId",
                "Union": "UnionId",
            },
        )
    )
