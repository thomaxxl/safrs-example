#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from safrs import SAFRSBase
from safrs.api_methods import search
from sqlalchemy import BOOLEAN, DECIMAL, Column, Date, ForeignKey, Integer, String, Text, create_engine
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


class Customer(BaseModel):
    __tablename__ = "Customer"

    Id = Column(String, primary_key=True)
    CompanyName = Column(String)
    ContactName = Column(String)
    City = Column(String)
    Country = Column(String)
    Phone = Column(String)
    Balance = Column(DECIMAL)
    CreditLimit = Column(DECIMAL)
    allow_client_generated_ids = True

    OrderList = relationship("Order", back_populates="Customer")


class Employee(BaseModel):
    __tablename__ = "Employee"

    Id = Column(Integer, primary_key=True)
    LastName = Column(String)
    FirstName = Column(String)
    Title = Column(String)
    Email = Column(Text)
    City = Column(String)
    Country = Column(String)

    OrderList = relationship("Order", back_populates="Employee")


class Order(BaseModel):
    __tablename__ = "Order"

    Id = Column(Integer, primary_key=True)
    CustomerId = Column(String, ForeignKey("Customer.Id"))
    EmployeeId = Column(Integer, ForeignKey("Employee.Id"))
    OrderDate = Column(String)
    RequiredDate = Column(Date)
    ShipCity = Column(String)
    ShipCountry = Column(String)
    Ready = Column(BOOLEAN)

    Customer = relationship("Customer", back_populates="OrderList")
    Employee = relationship("Employee", back_populates="OrderList")


EXPOSED_MODELS = [Customer, Employee, Order]

COLLECTION_ID_KEYS = {
    "Customer": "CustomerId",
    "Employee": "EmployeeId",
    "Order": "OrderId",
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
    return


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


def _seed_order(session: Any) -> Any:
    orders = session.query(Order).order_by(Order.Id.asc()).all()
    for order in orders:
        if getattr(order, "Customer", None) is None:
            continue
        if getattr(order, "Employee", None) is None:
            continue
        return order
    raise RuntimeError("Unable to build seed payload: no Order row has both Customer and Employee relationships")


def build_seed_payload(session: Any) -> dict[str, Any]:
    order = _seed_order(session)
    customer = order.Customer
    employee = order.Employee
    if customer is None or employee is None:
        raise RuntimeError("Unable to build seed payload: selected Order has incomplete relationships")

    order_id = _instance_jsonapi_id(order)
    customer_id = _instance_jsonapi_id(customer)
    employee_id = _instance_jsonapi_id(employee)

    relationships: dict[str, Any] = {
        "Customer.OrderList": {"data": [_instance_identifier(order)]},
        "Employee.OrderList": {"data": [_instance_identifier(order)]},
        "Order.Customer": {"data": _instance_identifier(customer)},
        "Order.Employee": {"data": _instance_identifier(employee)},
    }
    relationship_path_params: dict[str, dict[str, str]] = {
        "Customer.OrderList": {"CustomerId": customer_id},
        "Employee.OrderList": {"EmployeeId": employee_id},
        "Order.Customer": {"OrderId": order_id},
        "Order.Employee": {"OrderId": order_id},
    }

    return {
        "CustomerId": customer_id,
        "EmployeeId": employee_id,
        "OrderId": order_id,
        "collection_id_keys": dict(COLLECTION_ID_KEYS),
        "relationships": relationships,
        "relationship_path_params": relationship_path_params,
    }
