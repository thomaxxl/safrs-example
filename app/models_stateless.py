#!/usr/bin/env python3
#
# This example shows how you can implement a SAFRSBase object (the Test class)
# without a SQLAlchemy model
# It does require you to implement some attributes and methods yourself
#
import sys
import logging
from flask import Flask, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from safrs import SAFRSBase, SAFRSAPI, jsonapi_rpc
from safrs.safrs_types import SAFRSID
from safrs.util import classproperty
from collections import namedtuple
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOMANY  # , MANYTOONE
import pdb
from app.base_model import db, BaseModel

class User(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "Users2"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")
    books = db.relationship("Book2", back_populates="user", lazy="dynamic")


class Book2(SAFRSBase, db.Model):
    """
        description: Book description
    """

    __tablename__ = "Books2"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    user_id = db.Column(db.String, db.ForeignKey("Users2.id"))
    user = db.relationship("User", back_populates="books")

#
#
#


class TestQuery:
    """
        The safrs sqla serialization calls some sqlalchemy methods
        We emulate them here
    """
    def first(cls):
        return Test(name="name 0")

    def filter_by(cls, *args, **kwargs):
        return cls

    def count(cls, *args, **kwargs):
        return 100

    def offset(cls, offset):
        return cls

    def limit(cls, limit):
        return cls

    def all(cls):
        return [Test(name="name")]

    def order_by(cls, attr_name):
        return cls


class Mapper:
    class_ = Book2


class TestBookRelationship:
    key = "books"
    direction = ONETOMANY
    mapper = Mapper
    _target = [Book2]

    def __init__(self, parent):
        self.parent = parent
        
    def __iter__(self):
        """
            yield items from the collection that should be in the relationship
        """
        for book in Book22.query.all():
            yield book


class Test(SAFRSBase):
    """
        description: Book description
    """

    id = 1
    id_type = SAFRSID
    ja_type = "TestType"
    my_custom_field = ""
    books = TestBookRelationship

    def __new__(cls, *args, **kwargs):
        """
            override SAFRSBase.__new__
        """
        return object.__new__(cls)

    def __init__(self, *args, **kwargs):
        """
            Constructor
        """
        self.books = TestBookRelationship(self)
        self.name = kwargs.get("name")

    @classproperty
    def _s_type(cls):
        """
            json:api type
        """
        return cls.ja_type

    @classproperty
    def _s_query(cls):
        """
            query placeholder
        """
        return TestQuery()

    @classproperty
    def _s_relationships(cls):
        """
            return the included relationships
        """
        return [cls.books]

    @property
    def _s_jsonapi_attrs(self):
        """
            return the attributes kv pairs
        """
        return {"name": self.name, "my_custom_field": self.my_custom_field}

    @classproperty
    def _s_jsonapi_attrs(cls):
        """
            return the attribute names used to generate the swagger
        """
        return ["id", "name", "my_custom_field"]

    @classproperty
    def _s_url(self):
        """
            The URL to return in the jsonapi "links" parameter
        """
        return "http://safrs-example.com/api/Test"

    @classmethod
    def get_instance(cls, id, failsafe=False):
        """
            return the instance specified by id
        """
        result = Test()
        return result

    @classproperty
    def class_(cls):
        return cls


TestBookRelationship.parent = Test


if __name__ == "__main__":
    HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    PORT = 5000
    app = Flask("SAFRS Demo Application")
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///", DEBUG=True)
    db.init_app(app)
    db.app = app
    # Create the database
    db.create_all()
    API_PREFIX = ""

    with app.app_context():
        # Create a user and a book and add the book to the user.books relationship

        user = User(name="thomas", email="em@il")
        book = Book(name="test_book")
        user.books.append(book)
        api = SAFRSAPI(app, host="{}".format(HOST), port=PORT, prefix=API_PREFIX)
        # Expose the database objects as REST API endpoints
        api.expose_object(User)
        api.expose_object(Book)
        api.expose_object(Test)
        # Register the API at /api/docs
        print("Starting API: http://{}:{}{}".format(HOST, PORT, API_PREFIX))
        app.run(host=HOST, port=PORT)

