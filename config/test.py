# flake8: noqa: F405
#from .base import *  # noqa: F401,F403

import sys, os
sys.path.append(os.path.dirname(__file__))
from base import *

DEBUG = True
TESTING = True

DB_NAME = 'safrs_test'
DB_USER = 'postgres'
DB_PWD = 'password'
SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PWD}@{DB_HOST}/{DB_NAME}'
