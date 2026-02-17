import pytest

from safrs import SAFRSAPI, SAFRSBase
from safrs.errors import SystemValidationError
from app.base_model import db


def test_expose_object_rejects_legacy_s_expose_false(app):
    class HiddenLegacy(SAFRSBase, db.Model):
        __tablename__ = "hidden_legacy_expose_object_guard"
        _s_expose = False
        id = db.Column(db.Integer, primary_key=True)

    assert HiddenLegacy._s_expose is False
    with pytest.raises(SystemValidationError):
        SAFRSAPI.expose_object(None, HiddenLegacy)


def test_expose_object_rejects_safrs_config_expose_false(app):
    class HiddenConfig(SAFRSBase, db.Model):
        __tablename__ = "hidden_config_expose_object_guard"
        __safrs_config__ = {"expose": False, "pk_delimiter": "-"}
        id = db.Column(db.Integer, primary_key=True)

    assert HiddenConfig._s_expose is False
    assert HiddenConfig._s_pk_delimiter == "-"
    with pytest.raises(SystemValidationError):
        SAFRSAPI.expose_object(None, HiddenConfig)
