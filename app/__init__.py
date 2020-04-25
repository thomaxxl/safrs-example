import logging.config
import hashlib
import sys

import flask
import safrs
from flask import Flask
from safrs import SAFRSAPI
from flask_migrate import Migrate
from app.models import db, Thing, SubThing, Person, Book, Review, Publisher,ThingWOCommit, ThingWCommit, ThingWType, AuthUser
from app.models_stateless import Test
#from app.models import db, Thing, SubThing

migrate = Migrate()


def create_api(app, swagger_host=None, swagger_port=5000):
    custom_swagger = {
            "info": {"title": "New Title"},
            "securityDefinitions": {"ApiKeyAuth": {"type": "apiKey" , "in" : "header", "name": "My-ApiKey"}}
        }  # Customized swagger will be merged
    api = SAFRSAPI(app, host=swagger_host, port=swagger_port, custom_swagger=custom_swagger, decorators=[safrs.test_decorator])
    api.expose_object(Thing)
    api.expose_object(ThingWType)
    api.expose_object(SubThing)
    api.expose_object(ThingWOCommit)
    api.expose_object(ThingWCommit)
    api.expose_object(Test)
    api.expose_object(AuthUser)


    for i in range(30):
        secret = hashlib.sha256(bytes(i)).hexdigest()
        reader = Person(name="Reader " + str(i), email="reader_email" + str(i), password=secret)
        author = Person(name="Author " + str(i), email="author_email" + str(i))
        book = Book(title="book_title" + str(i))
        unexp_book = Book(title="unexp_book_title" + str(i))
        review = Review(
            reader_id=reader.id, book_id=book.id, review="review " + str(i)
        )
        if i % 4 == 0:
            publisher = Publisher(name="name" + str(i))
        publisher.books.append(book)
        publisher.books.append(unexp_book)
        reader.books_read.append(book)
        author.books_written.append(book)
        for obj in [reader, author, book, publisher, review]:
            db.session.add(obj)

        db.session.commit()

    for model in [Person, Book, Review, Publisher]:
        # Create an API endpoint
        api.expose_object(model)


def create_app():
    """This app factory omits starting SAFRSAPI to enable running the shell etc in a simpler way"""
    app = Flask("some-api")
    app.config.from_envvar("CONFIG_MODULE")
    logging.config.dictConfig(app.config.get("LOGGING", {}))
    db.init_app(app)
    migrate.init_app(app, db)
    return app


def run_app():
    app = create_app()
    with app.app_context():
        create_api(app, app.config["SWAGGER_HOST"], app.config["SWAGGER_PORT"])
    return app
