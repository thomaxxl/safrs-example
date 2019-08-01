import factory
import safrs

from app import models

db = safrs.DB


class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Set session last second to get the right session
        cls._meta.sqlalchemy_session = db.session
        return super()._create(model_class, *args, **kwargs)


class ThingFactory(BaseFactory):
    class Meta:
        model = models.Thing

    name = factory.Sequence(lambda n: "Thing %s" % n)


class SubThingFactory(BaseFactory):
    class Meta:
        model = models.SubThing

    name = factory.Sequence(lambda n: "SubThing %s" % n)
    thing = factory.SubFactory(ThingFactory)
