import hashlib

from fastapi import FastAPI
from safrs.fastapi import SafrsFastAPI

from app.base_model import db
from app.models import (
    AuthUser,
    Book,
    PKItem,
    Person,
    Publisher,
    Review,
    SubThing,
    Thing,
    ThingWCommit,
    ThingWOCommit,
    ThingWType,
    UserWithJsonapiAttr,
    UserWithPerms,
)
from app.models_stateless import Test


def create_fastapi_api(seed_data: bool = True) -> FastAPI:
    app = FastAPI(openapi_url="/swagger.json", docs_url="/docs", redoc_url=None)
    api = SafrsFastAPI(app)

    for model in [Thing, ThingWType, SubThing, ThingWOCommit, ThingWCommit, Test, AuthUser]:
        api.expose_object(model)

    if seed_data:
        for i in range(10):
            secret = hashlib.sha256(bytes(i)).hexdigest()
            reader = Person(name="Reader " + str(i), email="reader_email" + str(i), password=secret)
            author = Person(name="Author " + str(i), email="author_email" + str(i))
            book = Book(title="book_title" + str(i))
            unexp_book = Book(title="unexp_book_title" + str(i))
            review = Review(reader_id=reader.id, book_id=book.id, review="review " + str(i))
            if i % 4 == 0:
                publisher = Publisher(name="name" + str(i))
            publisher.books.append(book)
            publisher.books.append(unexp_book)
            reader.books_read.append(book)
            author.books_written.append(book)
            for obj in [reader, author, book, publisher, review]:
                db.session.add(obj)
            for i in range(20):
                item = PKItem(foo="item_" + str(i), bar="group_" + str((int)(i / 10)), pk_A=str(i), pk_B=str(i), id=8)
                user = UserWithPerms(name=f"name{i}", email="some@mail")
                db.session.add(item)
                db.session.add(user)
            db.session.commit()

    for model in [Person, Book, Review, Publisher, PKItem, UserWithJsonapiAttr, UserWithPerms]:
        api.expose_object(model)

    return app
