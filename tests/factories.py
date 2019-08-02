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


class BookFactory(BaseFactory):
    class Meta:
        model = models.Book

    name = factory.Sequence(lambda n: "Book  %s" % n)


class PersonFactory(BaseFactory):
    class Meta:
        model = models.Person

    name = factory.Sequence(lambda n: "Person %s" % n)

    @factory.post_generation
    def books_read(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            self.posts = extracted


class PublisherFactory(BaseFactory):
    class Meta:
        model = models.Publisher

    name = factory.Sequence(lambda n: "Publisher %s" % n)

    @factory.post_generation
    def books(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            self.posts = extracted


class ThingFactory(BaseFactory):
    class Meta:
        model = models.Thing

    name = factory.Sequence(lambda n: "Thing %s" % n)


class SubThingFactory(BaseFactory):
    class Meta:
        model = models.SubThing

    name = factory.Sequence(lambda n: "SubThing %s" % n)
    thing = factory.SubFactory(ThingFactory)
