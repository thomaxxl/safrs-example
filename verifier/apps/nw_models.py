#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from safrs import SAFRSBase
from safrs.api_methods import search
from sqlalchemy import (
    Boolean,
    Column,
    DECIMAL,
    Date,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    Text,
    create_engine,
    text,
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, relationship, scoped_session, sessionmaker

DESCRIPTION = """
<a href=http://jsonapi.org>Json:API</a> compliant API built with SAFRS<br/>
- verifier app models backed by an existing SQLite database
"""

API_PREFIX = "/api"


class Base(DeclarativeBase):
    pass


class SAFRSDBWrapper:
    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


class BaseModel(SAFRSBase, Base):
    __abstract__ = True
    db_commit = False
    setattr(SAFRSBase, "search", search)


class Category(BaseModel):
    __tablename__ = "CategoryTableNameTest"
    _s_collection_name = "Category"

    Id = Column(Integer, primary_key=True)
    CategoryName_ColumnName = Column(String(8000))
    Description = Column(String(8000))
    Client_id = Column(Integer)

    ProductList = relationship("Product", back_populates="Category")


class Customer(BaseModel):
    __tablename__ = "Customer"
    _s_collection_name = "Customer"

    Id = Column(String, primary_key=True)
    CompanyName = Column(String)
    ContactName = Column(String)
    ContactTitle = Column(String)
    Address = Column(String)
    City = Column(String)
    Region = Column(String)
    PostalCode = Column(String)
    Country = Column(String)
    Phone = Column(String)
    Fax = Column(String)
    Balance = Column(DECIMAL)
    CreditLimit = Column(DECIMAL)
    OrderCount = Column(Integer, server_default=text("0"))
    UnpaidOrderCount = Column(Integer, server_default=text("0"))
    Client_id = Column(Integer)
    allow_client_generated_ids = True

    OrderList = relationship("Order", back_populates="Customer")


class CustomerDemographic(BaseModel):
    __tablename__ = "CustomerDemographic"
    _s_collection_name = "CustomerDemographic"

    Id = Column(String, primary_key=True)
    CustomerDesc = Column(String)
    allow_client_generated_ids = True


class Department(BaseModel):
    __tablename__ = "Department"
    _s_collection_name = "Department"

    Id = Column(Integer, primary_key=True)
    DepartmentId = Column(ForeignKey("Department.Id"))
    DepartmentName = Column(String(100))
    SecurityLevel = Column(Integer, server_default=text("0"))

    Department = relationship("Department", remote_side="Department.Id", back_populates="DepartmentList")
    DepartmentList = relationship("Department", back_populates="Department")
    EmployeeList = relationship(
        "Employee",
        foreign_keys="Employee.OnLoanDepartmentId",
        back_populates="OnLoanDepartment",
    )
    WorksForEmployeeList = relationship(
        "Employee",
        foreign_keys="Employee.WorksForDepartmentId",
        back_populates="WorksForDepartment",
    )


class Location(BaseModel):
    __tablename__ = "Location"
    _s_collection_name = "Location"

    country = Column(String(50), primary_key=True)
    city = Column(String(50), primary_key=True)
    notes = Column(String(256))
    allow_client_generated_ids = True

    OrderList = relationship("Order", back_populates="Location")


t_ProductDetails_View = Table(
    "ProductDetails_View",
    Base.metadata,
    Column("Id", Integer),
    Column("ProductName", String(8000)),
    Column("SupplierId", Integer),
    Column("CategoryId", Integer),
    Column("QuantityPerUnit", String(8000)),
    Column("UnitPrice", DECIMAL),
    Column("UnitsInStock", Integer),
    Column("UnitsOnOrder", Integer),
    Column("ReorderLevel", Integer),
    Column("Discontinued", Integer),
    Column("UnitsShipped", Integer),
    Column("CategoryName_ColumnName", String(8000)),
    Column("CategoryDescription", String(8000)),
    Column("SupplierName", String(8000)),
    Column("SupplierRegion", String(8000)),
)


class Region(BaseModel):
    __tablename__ = "Region"
    _s_collection_name = "Region"

    Id = Column(Integer, primary_key=True)
    RegionDescription = Column(String(8000))


class SampleDBVersion(BaseModel):
    __tablename__ = "SampleDBVersion"
    _s_collection_name = "SampleDBVersion"

    Id = Column(Integer, primary_key=True)
    Notes = Column(String(800))


class Shipper(BaseModel):
    __tablename__ = "Shipper"
    _s_collection_name = "Shipper"

    Id = Column(Integer, primary_key=True)
    CompanyName = Column(String(8000))
    Phone = Column(String(8000))


class Supplier(BaseModel):
    __tablename__ = "Supplier"
    _s_collection_name = "Supplier"

    Id = Column(Integer, primary_key=True)
    CompanyName = Column(String(8000))
    ContactName = Column(String(8000))
    ContactTitle = Column(String(8000))
    Address = Column(String(8000))
    City = Column(String(8000))
    Region = Column(String(8000))
    PostalCode = Column(String(8000))
    Country = Column(String(8000))
    Phone = Column(String(8000))
    Fax = Column(String(8000))
    HomePage = Column(String(8000))


class Territory(BaseModel):
    __tablename__ = "Territory"
    _s_collection_name = "Territory"

    Id = Column(String(8000), primary_key=True)
    TerritoryDescription = Column(String(8000))
    RegionId = Column(Integer, nullable=False)
    allow_client_generated_ids = True

    EmployeeTerritoryList = relationship("EmployeeTerritory", back_populates="Territory")


class Union(BaseModel):
    __tablename__ = "Union"
    _s_collection_name = "Union"

    Id = Column(Integer, primary_key=True)
    Name = Column(String(80))

    EmployeeList = relationship("Employee", back_populates="Union")


class Employee(BaseModel):
    __tablename__ = "Employee"
    _s_collection_name = "Employee"

    Id = Column(Integer, primary_key=True)
    LastName = Column(String)
    FirstName = Column(String)
    Title = Column(String)
    TitleOfCourtesy = Column(String)
    BirthDate = Column(String)
    HireDate = Column(String)
    Address = Column(String)
    Region = Column(String)
    PostalCode = Column(String)
    HomePhone = Column(String)
    Extension = Column(String)
    Notes = Column(String)
    ReportsTo = Column(Integer, index=True)
    PhotoPath = Column(String)
    EmployeeType = Column(String(16), server_default=text("Salaried"))
    Salary = Column(DECIMAL)
    WorksForDepartmentId = Column(ForeignKey("Department.Id"))
    OnLoanDepartmentId = Column(ForeignKey("Department.Id"))
    UnionId = Column(ForeignKey("Union.Id"))
    Dues = Column(DECIMAL)
    Email = Column(Text)
    City = Column(String)
    Country = Column(String)

    OnLoanDepartment = relationship(
        "Department",
        foreign_keys=[OnLoanDepartmentId],
        back_populates="EmployeeList",
    )
    Union = relationship("Union", back_populates="EmployeeList")
    WorksForDepartment = relationship(
        "Department",
        foreign_keys=[WorksForDepartmentId],
        back_populates="WorksForEmployeeList",
    )
    EmployeeAuditList = relationship("EmployeeAudit", back_populates="Employee")
    EmployeeTerritoryList = relationship("EmployeeTerritory", back_populates="Employee")
    OrderList = relationship("Order", back_populates="Employee")


class Product(BaseModel):
    __tablename__ = "Product"
    _s_collection_name = "Product"

    Id = Column(Integer, primary_key=True)
    ProductName = Column(String(8000))
    SupplierId = Column(Integer, nullable=False)
    CategoryId = Column(ForeignKey("CategoryTableNameTest.Id"), nullable=False)
    QuantityPerUnit = Column(String(8000))
    UnitPrice = Column(DECIMAL, nullable=False)
    UnitsInStock = Column(Integer, nullable=False)
    UnitsOnOrder = Column(Integer, nullable=False)
    ReorderLevel = Column(Integer, nullable=False)
    Discontinued = Column(Integer, nullable=False)
    UnitsShipped = Column(Integer)

    Category = relationship("Category", back_populates="ProductList")
    OrderDetailList = relationship("OrderDetail", back_populates="Product")


class EmployeeAudit(BaseModel):
    __tablename__ = "EmployeeAudit"
    _s_collection_name = "EmployeeAudit"

    Id = Column(Integer, primary_key=True)
    Title = Column(String)
    Salary = Column(DECIMAL)
    LastName = Column(String)
    FirstName = Column(String)
    EmployeeId = Column(ForeignKey("Employee.Id"))
    CreatedOn = Column(Text)
    UpdatedOn = Column(Text)
    CreatedBy = Column(Text)
    UpdatedBy = Column(Text)

    Employee = relationship("Employee", back_populates="EmployeeAuditList")


class EmployeeTerritory(BaseModel):
    __tablename__ = "EmployeeTerritory"
    _s_collection_name = "EmployeeTerritory"

    Id = Column(String(8000), primary_key=True)
    EmployeeId = Column(ForeignKey("Employee.Id"), nullable=False)
    TerritoryId = Column(ForeignKey("Territory.Id"))
    allow_client_generated_ids = True

    Employee = relationship("Employee", back_populates="EmployeeTerritoryList")
    Territory = relationship("Territory", back_populates="EmployeeTerritoryList")


class Order(BaseModel):
    __tablename__ = "Order"
    _s_collection_name = "Order"
    __table_args__ = (
        ForeignKeyConstraint(["Country", "City"], ["Location.country", "Location.city"]),
    )

    Id = Column(Integer, primary_key=True)
    CustomerId = Column(String, ForeignKey("Customer.Id"))
    EmployeeId = Column(Integer, ForeignKey("Employee.Id"))
    OrderDate = Column(String)
    RequiredDate = Column(Date)
    ShippedDate = Column(String)
    ShipVia = Column(Integer)
    Freight = Column(DECIMAL, server_default=text("0"))
    ShipName = Column(String)
    ShipAddress = Column(String)
    ShipCity = Column(String)
    ShipRegion = Column(String)
    ShipPostalCode = Column(String)
    ShipCountry = Column(String)
    AmountTotal = Column(DECIMAL(10, 2))
    Country = Column(String(50))
    City = Column(String(50))
    Ready = Column(Boolean)
    OrderDetailCount = Column(Integer, server_default=text("0"))
    CloneFromOrder = Column(ForeignKey("Order.Id"))

    Order = relationship("Order", remote_side="Order.Id", back_populates="OrderList")
    Location = relationship("Location", back_populates="OrderList")
    Customer = relationship("Customer", back_populates="OrderList")
    Employee = relationship("Employee", back_populates="OrderList")
    OrderList = relationship("Order", back_populates="Order")
    OrderDetailList = relationship("OrderDetail", back_populates="Order")

class OrderDetail(BaseModel):
    __tablename__ = "OrderDetail"
    _s_collection_name = "OrderDetail"

    Id = Column(Integer, primary_key=True)
    OrderId = Column(ForeignKey("Order.Id"), nullable=False)
    ProductId = Column(ForeignKey("Product.Id"), nullable=False)
    UnitPrice = Column(DECIMAL)
    Quantity = Column(Integer, server_default=text("1"), nullable=False)
    Discount = Column(Double, server_default=text("0"))
    Amount = Column(DECIMAL)
    ShippedDate = Column(String)

    Order = relationship("Order", back_populates="OrderDetailList")
    Product = relationship("Product", back_populates="OrderDetailList")


EXPOSED_MODELS = [
    Category,
    Customer,
    CustomerDemographic,
    Department,
    Employee,
    EmployeeAudit,
    EmployeeTerritory,
    Location,
    Order,
    OrderDetail,
    Product,
    Region,
    SampleDBVersion,
    Shipper,
    Supplier,
    Territory,
    Union,
]

COLLECTION_ID_KEYS = {
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
}
MODEL_BY_COLLECTION = {
    "Category": Category,
    "Customer": Customer,
    "CustomerDemographic": CustomerDemographic,
    "Department": Department,
    "Employee": Employee,
    "EmployeeAudit": EmployeeAudit,
    "EmployeeTerritory": EmployeeTerritory,
    "Location": Location,
    "Order": Order,
    "OrderDetail": OrderDetail,
    "Product": Product,
    "Region": Region,
    "SampleDBVersion": SampleDBVersion,
    "Shipper": Shipper,
    "Supplier": Supplier,
    "Territory": Territory,
    "Union": Union,
}


def create_session(
    db_path: Path | None = None,
    database_url: str | None = None,
    scopefunc: Callable[[], Any] | None = None,
) -> Any:
    if database_url:
        engine = create_engine(str(database_url), future=True)
    else:
        if db_path is None:
            raise ValueError("db_path is required when database_url is not provided")
        engine = create_engine(f"sqlite:///{db_path}", future=True)

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    if scopefunc is not None:
        Session = scoped_session(session_factory, scopefunc=scopefunc)
    else:
        Session = scoped_session(session_factory)
    return Session


def seed_data(_session: Any) -> None:
    # The NW verifier app runs against an already-populated SQLite database.
    # Add minimal rows for known empty tables to keep seed/path-parameter patching stable.
    changed = False
    if _session.query(CustomerDemographic).count() == 0:
        _session.add(CustomerDemographic(Id="CD-SEED", CustomerDesc="seed row"))
        changed = True
    if changed:
        _session.commit()


def _instance_jsonapi_id(instance: Any) -> str:
    value = getattr(instance, "jsonapi_id", None)
    if value in (None, ""):
        value = getattr(instance, "Id", None)
    return str(value)


def _instance_identifier(instance: Any) -> dict[str, str]:
    return {
        "type": str(getattr(instance, "_s_type", type(instance).__name__)),
        "id": _instance_jsonapi_id(instance),
    }


def _relationship_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "all") and callable(value.all):
        return list(value.all())
    if isinstance(value, list):
        return list(value)
    try:
        return list(value)
    except Exception:
        return []


def _collection_name(model_cls: type[BaseModel]) -> str:
    value = getattr(model_cls, "_s_collection_name", None)
    if isinstance(value, str) and value:
        return value
    return model_cls.__name__


def _ordered_query(session: Any, model_cls: type[BaseModel]) -> Any:
    query = session.query(model_cls)
    mapper = sa_inspect(model_cls)
    for column in mapper.primary_key:
        query = query.order_by(column.asc())
    return query


def _first_instance(session: Any, model_cls: type[BaseModel]) -> Any:
    return _ordered_query(session, model_cls).first()


def _first_parent_with_relationship(
    session: Any,
    model_cls: type[BaseModel],
    rel_name: str,
    *,
    uselist: bool,
) -> tuple[Any, list[Any]]:
    for parent in _ordered_query(session, model_cls).all():
        value = getattr(parent, rel_name)
        if uselist:
            related = _relationship_items(value)
            if related:
                related = sorted(related, key=_instance_jsonapi_id)
                return parent, related
            continue
        if value is not None:
            return parent, [value]
    return None, []


def build_seed_payload(session: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "collection_id_keys": dict(COLLECTION_ID_KEYS),
        "relationships": {},
        "relationship_path_params": {},
    }

    missing_ids: list[str] = []
    first_instances: dict[str, Any] = {}
    for collection, seed_key in COLLECTION_ID_KEYS.items():
        model_cls = MODEL_BY_COLLECTION[collection]
        instance = _first_instance(session, model_cls)
        if instance is None:
            missing_ids.append(seed_key)
            continue
        first_instances[collection] = instance
        payload[seed_key] = _instance_jsonapi_id(instance)

    if missing_ids:
        raise RuntimeError(f"Unable to build NW seed payload; missing rows for: {', '.join(sorted(missing_ids))}")

    relationships = payload["relationships"]
    relationship_path_params = payload["relationship_path_params"]
    for collection, model_cls in MODEL_BY_COLLECTION.items():
        parent_seed_key = COLLECTION_ID_KEYS.get(collection)
        if not parent_seed_key:
            continue
        parent_model = first_instances.get(collection)
        if parent_model is None:
            continue
        mapper = sa_inspect(model_cls)
        for relationship in mapper.relationships:
            rel_name = str(relationship.key)
            parent, children = _first_parent_with_relationship(
                session,
                model_cls,
                rel_name,
                uselist=bool(relationship.uselist),
            )
            if parent is None or not children:
                continue

            seed_relationship_key = f"{_collection_name(model_cls)}.{rel_name}"
            relationship_path_params[seed_relationship_key] = {
                parent_seed_key: _instance_jsonapi_id(parent),
            }
            if relationship.uselist:
                relationships[seed_relationship_key] = {"data": [_instance_identifier(children[0])]}
            else:
                relationships[seed_relationship_key] = {"data": _instance_identifier(children[0])}

    return payload
