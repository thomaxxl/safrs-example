import safrs
from flask_sqlalchemy import SQLAlchemy
from safrs import SAFRSBase, SAFRSAPI
from safrs.util import classproperty

safrs.DB = db = SQLAlchemy()

#db = safrs.DB


class BaseModel(safrs.SAFRSBase, db.Model):
    __abstract__ = True
    # Enables us to handle db session ourselves
    db_commit = False

    # Override SAFRS __str__ with custom repr
    def __str__(self):
        return repr(self)

    def __repr__(self):
        return "<{}: id={}{}>".format(
            self.__class__.__name__,
            self.id,
            f" name={self.name}" if hasattr(self, "name") else "",
        )
