from safrs import jsonapi_rpc, SAFRSFormattedResponse, jsonapi_format_response
from safrs.api_methods import startswith
from sqlalchemy import func

from app.base_model import db, BaseModel


class Thing(BaseModel):
    """
        description: Thing related operations
    """
    __tablename__ = "thing"

    id = db.Column(db.String, primary_key=True, server_default=func.uuid_generate_v1())
    name = db.Column(db.String)
    description = db.Column(db.String)

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


class SubThing(BaseModel):
    __tablename__ = "subthing"

    id = db.Column(db.String, primary_key=True, server_default=func.uuid_generate_v1())
    name = db.Column(db.String, nullable=False)

    thing_id = db.Column(db.String, db.ForeignKey("thing.id"))
    thing = db.relationship("Thing", foreign_keys=thing_id)
