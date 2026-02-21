#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, List

from safrs import SAFRSBase
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
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship, scoped_session, sessionmaker

API_PREFIX = "/api"
DESCRIPTION = "SAFRS FastAPI app exposing cleaned models derived from /tmp/models.py"
DEFAULT_DB_PATH = Path("/home/t/lab/ALS/ApiLogicProject/database/db.sqlite")


class Base(DeclarativeBase):
    pass


metadata = Base.metadata


class BaseModel(SAFRSBase, Base):
    __abstract__ = True
    db_commit = False


class SAFRSDBWrapper:
    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


def create_session(db_path: Path) -> Any:
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return scoped_session(session_factory)


class Category(BaseModel):  # type: ignore
    __tablename__ = 'CategoryTableNameTest'
    _s_collection_name = 'Category'  # type: ignore

    Id = Column(Integer, primary_key=True)
    CategoryName_ColumnName = Column(String(8000))
    Description = Column(String(8000))
    Client_id = Column(Integer)

    # parent relationships (access parent)

    # child relationships (access children)
    ProductList : Mapped[List["Product"]] = relationship(back_populates="Category")



class Customer(BaseModel):  # type: ignore
    __tablename__ = 'Customer'
    _s_collection_name = 'Customer'  # type: ignore

    Id = Column(String(8000), primary_key=True)
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
    Balance : DECIMAL = Column(DECIMAL)
    CreditLimit : DECIMAL = Column(DECIMAL)
    OrderCount = Column(Integer, server_default=text("0"))
    UnpaidOrderCount = Column(Integer, server_default=text("0"))
    Client_id = Column(Integer)
    allow_client_generated_ids = True

    # parent relationships (access parent)

    # child relationships (access children)
    OrderList : Mapped[List["Order"]] = relationship(back_populates="Customer")



class CustomerDemographic(BaseModel):  # type: ignore
    __tablename__ = 'CustomerDemographic'
    _s_collection_name = 'CustomerDemographic'  # type: ignore

    Id = Column(String(8000), primary_key=True)
    CustomerDesc = Column(String(8000))
    allow_client_generated_ids = True

    # parent relationships (access parent)

    # child relationships (access children)



class Department(BaseModel):  # type: ignore
    __tablename__ = 'Department'
    _s_collection_name = 'Department'  # type: ignore

    Id = Column(Integer, primary_key=True)
    DepartmentId = Column(ForeignKey('Department.Id'))
    DepartmentName = Column(String(100))
    SecurityLevel = Column(Integer, server_default=text("0"))

    # parent relationships (access parent)
    Department : Mapped["Department"] = relationship(remote_side=[Id], back_populates=("DepartmentList"))

    # child relationships (access children)
    DepartmentList : Mapped[List["Department"]] = relationship(back_populates="Department")
    EmployeeList : Mapped[List["Employee"]] = relationship(foreign_keys='[Employee.OnLoanDepartmentId]', back_populates="OnLoanDepartment")
    WorksForEmployeeList : Mapped[List["Employee"]] = relationship(foreign_keys='[Employee.WorksForDepartmentId]', back_populates="WorksForDepartment")



class Location(BaseModel):  # type: ignore
    __tablename__ = 'Location'
    _s_collection_name = 'Location'  # type: ignore

    country = Column(String(50), primary_key=True)
    city = Column(String(50), primary_key=True)
    notes = Column(String(256))
    allow_client_generated_ids = True

    # parent relationships (access parent)

    # child relationships (access children)
    OrderList : Mapped[List["Order"]] = relationship(back_populates="Location")



t_ProductDetails_View = Table(
    'ProductDetails_View', metadata,
    Column('Id', Integer),
    Column('ProductName', String(8000)),
    Column('SupplierId', Integer),
    Column('CategoryId', Integer),
    Column('QuantityPerUnit', String(8000)),
    Column('UnitPrice', DECIMAL),
    Column('UnitsInStock', Integer),
    Column('UnitsOnOrder', Integer),
    Column('ReorderLevel', Integer),
    Column('Discontinued', Integer),
    Column('UnitsShipped', Integer),
    Column('CategoryName_ColumnName', String(8000)),
    Column('CategoryDescription', String(8000)),
    Column('SupplierName', String(8000)),
    Column('SupplierRegion', String(8000))
)


class Region(BaseModel):  # type: ignore
    __tablename__ = 'Region'
    _s_collection_name = 'Region'  # type: ignore

    Id = Column(Integer, primary_key=True)
    RegionDescription = Column(String(8000))

    # parent relationships (access parent)

    # child relationships (access children)



class SampleDBVersion(BaseModel):  # type: ignore
    __tablename__ = 'SampleDBVersion'
    _s_collection_name = 'SampleDBVersion'  # type: ignore

    Id = Column(Integer, primary_key=True)
    Notes = Column(String(800))

    # parent relationships (access parent)

    # child relationships (access children)



class Shipper(BaseModel):  # type: ignore
    __tablename__ = 'Shipper'
    _s_collection_name = 'Shipper'  # type: ignore

    Id = Column(Integer, primary_key=True)
    CompanyName = Column(String(8000))
    Phone = Column(String(8000))

    # parent relationships (access parent)

    # child relationships (access children)



class Supplier(BaseModel):  # type: ignore
    __tablename__ = 'Supplier'
    _s_collection_name = 'Supplier'  # type: ignore

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

    # parent relationships (access parent)

    # child relationships (access children)



class Territory(BaseModel):  # type: ignore
    __tablename__ = 'Territory'
    _s_collection_name = 'Territory'  # type: ignore

    Id = Column(String(8000), primary_key=True)
    TerritoryDescription = Column(String(8000))
    RegionId = Column(Integer, nullable=False)
    allow_client_generated_ids = True

    # parent relationships (access parent)

    # child relationships (access children)
    EmployeeTerritoryList : Mapped[List["EmployeeTerritory"]] = relationship(back_populates="Territory")



class Union(BaseModel):  # type: ignore
    __tablename__ = 'Union'
    _s_collection_name = 'Union'  # type: ignore

    Id = Column(Integer, primary_key=True)
    Name = Column(String(80))

    # parent relationships (access parent)

    # child relationships (access children)
    EmployeeList : Mapped[List["Employee"]] = relationship(back_populates="Union")



class Employee(BaseModel):  # type: ignore
    __tablename__ = 'Employee'
    _s_collection_name = 'Employee'  # type: ignore

    Id = Column(Integer, primary_key=True)
    LastName = Column(String(8000))
    FirstName = Column(String(8000))
    Title = Column(String(8000))
    TitleOfCourtesy = Column(String(8000))
    BirthDate = Column(String(8000))
    HireDate = Column(String(8000))
    Address = Column(String(8000))
    City = Column(String(8000))
    Region = Column(String(8000))
    PostalCode = Column(String(8000))
    Country = Column(String(8000))
    HomePhone = Column(String(8000))
    Extension = Column(String(8000))
    Notes = Column(String(8000))
    ReportsTo = Column(Integer, index=True)
    PhotoPath = Column(String(8000))
    EmployeeType = Column(String(16), server_default=text("Salaried"))
    Salary : DECIMAL = Column(DECIMAL)
    WorksForDepartmentId = Column(ForeignKey('Department.Id'))
    OnLoanDepartmentId = Column(ForeignKey('Department.Id'))
    UnionId = Column(ForeignKey('Union.Id'))
    Dues : DECIMAL = Column(DECIMAL)
    Email = Column(Text)

    # parent relationships (access parent)
    OnLoanDepartment : Mapped["Department"] = relationship(foreign_keys='[Employee.OnLoanDepartmentId]', back_populates=("EmployeeList"))
    Union : Mapped["Union"] = relationship(back_populates=("EmployeeList"))
    WorksForDepartment : Mapped["Department"] = relationship(foreign_keys='[Employee.WorksForDepartmentId]', back_populates=("WorksForEmployeeList"))

    # child relationships (access children)
    EmployeeAuditList : Mapped[List["EmployeeAudit"]] = relationship(back_populates="Employee")
    EmployeeTerritoryList : Mapped[List["EmployeeTerritory"]] = relationship(back_populates="Employee")
    OrderList : Mapped[List["Order"]] = relationship(back_populates="Employee")



class Product(BaseModel):  # type: ignore
    __tablename__ = 'Product'
    _s_collection_name = 'Product'  # type: ignore

    Id = Column(Integer, primary_key=True)
    ProductName = Column(String(8000))
    SupplierId = Column(Integer, nullable=False)
    CategoryId = Column(ForeignKey('CategoryTableNameTest.Id'), nullable=False)
    QuantityPerUnit = Column(String(8000))
    UnitPrice : DECIMAL = Column(DECIMAL, nullable=False)
    UnitsInStock = Column(Integer, nullable=False)
    UnitsOnOrder = Column(Integer, nullable=False)
    ReorderLevel = Column(Integer, nullable=False)
    Discontinued = Column(Integer, nullable=False)
    UnitsShipped = Column(Integer)

    # parent relationships (access parent)
    Category : Mapped["Category"] = relationship(back_populates=("ProductList"))

    # child relationships (access children)
    OrderDetailList : Mapped[List["OrderDetail"]] = relationship(back_populates="Product")



class EmployeeAudit(BaseModel):  # type: ignore
    __tablename__ = 'EmployeeAudit'
    _s_collection_name = 'EmployeeAudit'  # type: ignore

    Id = Column(Integer, primary_key=True)
    Title = Column(String)
    Salary : DECIMAL = Column(DECIMAL)
    LastName = Column(String)
    FirstName = Column(String)
    EmployeeId = Column(ForeignKey('Employee.Id'))
    CreatedOn = Column(Text)
    UpdatedOn = Column(Text)
    CreatedBy = Column(Text)
    UpdatedBy = Column(Text)

    # parent relationships (access parent)
    Employee : Mapped["Employee"] = relationship(back_populates=("EmployeeAuditList"))

    # child relationships (access children)



class EmployeeTerritory(BaseModel):  # type: ignore
    __tablename__ = 'EmployeeTerritory'
    _s_collection_name = 'EmployeeTerritory'  # type: ignore

    Id = Column(String(8000), primary_key=True)
    EmployeeId = Column(ForeignKey('Employee.Id'), nullable=False)
    TerritoryId = Column(ForeignKey('Territory.Id'))
    allow_client_generated_ids = True

    # parent relationships (access parent)
    Employee : Mapped["Employee"] = relationship(back_populates=("EmployeeTerritoryList"))
    Territory : Mapped["Territory"] = relationship(back_populates=("EmployeeTerritoryList"))

    # child relationships (access children)



class Order(BaseModel):  # type: ignore
    __tablename__ = 'Order'
    _s_collection_name = 'Order'  # type: ignore
    __table_args__ = (
        ForeignKeyConstraint(['Country', 'City'], ['Location.country', 'Location.city']),
    )

    Id = Column(Integer, primary_key=True)
    CustomerId = Column(ForeignKey('Customer.Id'), nullable=False, index=True)
    EmployeeId = Column(ForeignKey('Employee.Id'), nullable=False, index=True)
    OrderDate = Column(String(8000))
    RequiredDate = Column(Date)
    ShippedDate = Column(String(8000))
    ShipVia = Column(Integer)
    Freight : DECIMAL = Column(DECIMAL, server_default=text("0"))
    ShipName = Column(String(8000))
    ShipAddress = Column(String(8000))
    ShipCity = Column(String(8000))
    ShipRegion = Column(String(8000))
    ShipPostalCode = Column(String(8000))
    ShipCountry = Column(String(8000))
    AmountTotal : DECIMAL = Column(DECIMAL(10, 2))
    Country = Column(String(50))
    City = Column(String(50))
    Ready = Column(Boolean)
    OrderDetailCount = Column(Integer, server_default=text("0"))
    CloneFromOrder = Column(ForeignKey('Order.Id'))

    # parent relationships (access parent)
    Order : Mapped["Order"] = relationship(remote_side=[Id], back_populates=("OrderList"))
    Location : Mapped["Location"] = relationship(back_populates=("OrderList"))
    Customer : Mapped["Customer"] = relationship(back_populates=("OrderList"))
    Employee : Mapped["Employee"] = relationship(back_populates=("OrderList"))

    # child relationships (access children)
    OrderList : Mapped[List["Order"]] = relationship(back_populates="Order")
    OrderDetailList : Mapped[List["OrderDetail"]] = relationship(back_populates="Order")



class OrderDetail(BaseModel):  # type: ignore
    __tablename__ = 'OrderDetail'
    _s_collection_name = 'OrderDetail'  # type: ignore

    Id = Column(Integer, primary_key=True)
    OrderId = Column(ForeignKey('Order.Id'), nullable=False)
    ProductId = Column(ForeignKey('Product.Id'), nullable=False)
    UnitPrice : DECIMAL = Column(DECIMAL)
    Quantity = Column(Integer, server_default=text("1"), nullable=False)
    Discount = Column(Double, server_default=text("0"))
    Amount : DECIMAL = Column(DECIMAL)
    ShippedDate = Column(String(8000))

    # parent relationships (access parent)
    Order : Mapped["Order"] = relationship(back_populates=("OrderDetailList"))
    Product : Mapped["Product"] = relationship(back_populates=("OrderDetailList"))

    # child relationships (access children)

EXPOSED_MODELS = [
    Category,
    Customer,
    CustomerDemographic,
    Department,
    Location,
    Region,
    SampleDBVersion,
    Shipper,
    Supplier,
    Territory,
    Union,
    Employee,
    Product,
    EmployeeAudit,
    EmployeeTerritory,
    Order,
    OrderDetail,
]
