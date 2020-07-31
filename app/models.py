from safrs import jsonapi_rpc, SAFRSFormattedResponse, jsonapi_format_response, paginate
from safrs.api_methods import startswith, duplicate
from sqlalchemy import func
from app.base_model import db, BaseModel
from safrs import SAFRSBase, jsonapi_attr
from safrs.safrs_types import SafeString
from flask_httpauth import HTTPBasicAuth
import datetime
import hashlib

class HiddenColumn(db.Column):
    """
        The "expose" attribute indicates that the column shouldn't be exposed
    """

    permissions = "w"


class DocumentedColumn(db.Column):
    """
        The class attributes are used for the swagger
    """
    description = "My custom column description"
    swagger_type = "string"
    swagger_format = "string"
    name_format = "filter[{}]" # Format string with the column name as argument
    required = False
    default_filter = ""


class Thing(BaseModel):
    """
        description: Thing related operations
    """
    __tablename__ = "thing"

    id = db.Column(db.String, primary_key=True, server_default=func.uuid_generate_v1())
    name = db.Column(db.String)
    #description = db.Column("a_description", SafeString)
    description = db.Column("description", SafeString)
    created = db.Column(db.DateTime)
    documented_column = DocumentedColumn(db.String)

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

    @jsonapi_rpc(http_methods=["POST", "GET"])
    def none(self):
        return {}

    @jsonapi_attr
    def some_attr(self):
        """
            default: 
                - 200
        """
        return 100

class SubThing(BaseModel):
    __tablename__ = "subthing"
    _s_auto_commit = True
    id = db.Column(db.String, primary_key=True, server_default=func.uuid_generate_v1())
    name = db.Column(db.String, nullable=False)

    thing_id = db.Column(db.String, db.ForeignKey("thing.id"))
    thing = db.relationship("Thing", foreign_keys=thing_id)


class ThingWType(BaseModel):
    __tablename__ = "thing_with_type"
    db_commit = True
    id = db.Column(db.String, primary_key=True, server_default=func.uuid_generate_v1())
    type= db.Column(db.String, nullable=False,default="type_str")


class ThingWCommit(BaseModel):
    __tablename__ = "thing_with_commit"
    db_commit = True
    id = db.Column(db.String, primary_key=True, server_default=func.uuid_generate_v1())
    name = db.Column(db.String)
    description = db.Column(db.String)


class ThingWOCommit(BaseModel):
    __tablename__ = "thing_without_commit"
    db_commit = False
    id = db.Column(db.String, primary_key=True, server_default=func.uuid_generate_v1())
    name = db.Column(db.String)
 

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
    published = db.Column(db.Time)


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
    created = db.Column(db.DateTime)
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

    password = HiddenColumn(db.Text, default="")
    #exclude_attrs = ["password"]


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
    allow_client_generated_ids = True
    id = db.Column(db.Integer, primary_key=True)  # Integer pk instead of str
    name = db.Column(db.String, default="")
    books = db.relationship("Book", back_populates="publisher", lazy="dynamic")
    #books = db.relationship("Book", back_populates="publisher")
    duplicate = duplicate
    unexposed_books = db.relationship("UnexpBook", back_populates="publisher", lazy="dynamic")
    data = db.Column(db.JSON, default = {1:1})

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

class UnexpBook(db.Model):
    """
        description: Book description
    """

    __tablename__ = "UnexpBooks"
    id = db.Column(db.Integer, primary_key=True, auto_increment=True)
    name = db.Column(db.String, default="")
    publisher_id = db.Column(db.Integer, db.ForeignKey("Publishers.id"))
    publisher = db.relationship("Publisher", back_populates="unexposed_books")

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username_or_token, password):

    if username_or_token == "user" and password == "password":
        return True

    return False

def post_login_required(func):
    def post_decorator(*args, **kwargs):
        return auth.login_required(func)(*args, **kwargs)

    if func.__name__ in ("post", "patch", "delete"):
        return post_decorator

    return func


class AuthUser(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "auth_users"
    id = db.Column(db.String, primary_key=True)
    username = db.Column(db.String)
    decorators = [post_login_required]


class PKItem(SAFRSBase, db.Model):
    __tablename__ = "pk_items"
    id = db.Column(db.Integer, primary_key=True)
    pk_A = db.Column(db.String(32), primary_key=True)
    pk_B = db.Column(db.String(32), primary_key=True)
    #pk_B = db.Column(db.String(32))

    foo = db.Column(db.String(32))
    bar = db.Column(db.String(32))

class UserWithJsonapiAttr(SAFRSBase, db.Model):
    """
        description: User description
    """

    __tablename__ = "UsersWithJsonapiAttr"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)
    
    @jsonapi_attr
    def some_attr(self):
        return 'some_value'
    
    @some_attr.setter
    def some_attr(self, val):
        print("some_attr setter value:", val)
        self.name = val
