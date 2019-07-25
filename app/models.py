from safrs import jsonapi_rpc, SAFRSFormattedResponse, jsonapi_format_response, paginate
from safrs.api_methods import startswith
from sqlalchemy import func
from app.base_model import db, BaseModel
from safrs import SAFRSBase
import datetime
import hashlib


class Thing(BaseModel):
    """
        description: Thing related operations
    """
    __tablename__ = "thing"

    id = db.Column(db.String, primary_key=True, server_default=func.uuid_generate_v1())
    name = db.Column(db.String)
    description = db.Column(db.String)
    created = db.Column(db.DateTime)

    @classmethod
    @jsonapi_rpc(http_methods=["GET"])
    def get_by_name(cls, name, **kwargs):
        """
        description : Generate and return a Thing based on name
        parameters:
            - name: name
              type : string
        """
        thing = cls.query.filter_by(name=name).one_or_none()
        if not thing:
            # thing.description = populate_based_on_name()
            db.session.add(thing)
            db.session.commit()

        response = SAFRSFormattedResponse()
        result = jsonapi_format_response(thing, meta={}, count=1)
        response.response = result
        return response

    @jsonapi_rpc(http_methods=["POST", "GET"])
    def send_thing(self, email):
        """
        description : Send Thing to email
        args:
            email:
                type : string
                example : email@example.com
        """
        content = "Hello {}, here is your thing: {}\n".format(email, email)
        return {"result": "sent: {}".format(content)}

    startswith = startswith

    @classmethod
    def filter(cls, *args, **kwargs):
        return cls.query.all()


class SubThing(BaseModel):
    __tablename__ = "subthing"

    id = db.Column(db.String, primary_key=True, server_default=func.uuid_generate_v1())
    name = db.Column(db.String, nullable=False)

    thing_id = db.Column(db.String, db.ForeignKey("thing.id"))
    thing = db.relationship("Thing", foreign_keys=thing_id)

class Book(BaseModel):
    """
        description: Book description
    """

    __tablename__ = "Books"
    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String, default="")
    reader_id = db.Column(db.String, db.ForeignKey("People.id"))
    author_id = db.Column(db.String, db.ForeignKey("People.id"))
    publisher_id = db.Column(db.Integer, db.ForeignKey("Publishers.id"))
    publisher = db.relationship("Publisher", back_populates="books")
    reviews = db.relationship(
        "Review", backref="book", cascade="save-update, merge, delete, delete-orphan"
    )


class Person(BaseModel):
    """
        description: People description
    """

    __tablename__ = "People"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, default="")
    email = db.Column(db.String, default="")
    comment = db.Column(db.Text, default="")
    dob = db.Column(db.Date)
    books_read = db.relationship(
        "Book",
        backref="reader",
        foreign_keys=[Book.reader_id],
        cascade="save-update, merge",
    )
    books_written = db.relationship(
        "Book", backref="author", foreign_keys=[Book.author_id]
    )
    reviews = db.relationship("Review", backref="reader")

    password = db.Column(db.Text, default="")
    exclude_attrs = ["password"]

    # Following methods are exposed through the REST API
    @jsonapi_rpc(http_methods=["POST"])
    def send_mail(self, email):
        """
            description : Send an email
            args:
                email: test email
            parameters:
                - name : my_query_string_param
                  default : my_value
        """
        content = "Mail to {} : {}\n".format(self.name, email)
        with open("/tmp/mail.txt", "a+") as mailfile:
            mailfile.write(content)
        return {"result": "sent {}".format(content)}

    @classmethod
    @jsonapi_rpc(http_methods=["GET","POST"])
    def my_rpc(cls, *args, **kwargs):
        """
            description : Generate and return a jsonapi-formatted response
            pageable: false
            parameters:
                - name : my_query_string_param
                  default : my_value
            args:
                email: test email
        """
        print(args)
        print(kwargs)
        response = SAFRSFormattedResponse()
        try:
            instances = cls.query
            links, instances, count = paginate(instances)
            data = [item for item in instances]
            meta = {"args" : args, "kwargs" : kwargs}
            errors = None
            response.response = jsonapi_format_response(data, meta, links, errors, count)
        except Exception as exc:
            safrs.log.exception(exc)

        return response


class Publisher(BaseModel):
    """
        description: Publisher description
        ---
        demonstrate custom (de)serialization in __init__ and to_dict
    """

    __tablename__ = "Publishers"
    id = db.Column(db.Integer, primary_key=True)  # Integer pk instead of str
    name = db.Column(db.String, default="")
    #books = db.relationship("Book", back_populates="publisher", lazy="dynamic")
    books = db.relationship("Book", back_populates="publisher")

    def __init__(self, *args, **kwargs):
        custom_field = kwargs.pop("custom_field", None)
        super().__init__(self, **kwargs)

    def to_dict(self):
        result = SAFRSBase.to_dict(self)
        result["custom_field"] = "some customization"
        return result

    @classmethod
    def _s_filter(cls, arg):
        """
            Sample custom filtering, override this method to implement custom filtering
            using the sqlalchemy orm
        """
        return cls.query.filter_by(name=arg)


class Review(BaseModel):
    """
        description: Review description
    """

    __tablename__ = "Reviews"
    reader_id = db.Column(
        db.String, db.ForeignKey("People.id", ondelete="CASCADE"), primary_key=True
    )
    book_id = db.Column(db.String, db.ForeignKey("Books.id"), primary_key=True)
    review = db.Column(db.String, default="")
    created = db.Column(db.DateTime)
