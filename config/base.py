import os

DB_HOST = os.environ['DB_HOST']
DB_USER = os.environ['DB_USER']
DB_PWD = os.environ['DB_PWD']
DB_NAME = os.environ['DB_NAME']
SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PWD}@{DB_HOST}/{DB_NAME}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# feels dirty to hard code
SWAGGER_HOST = os.getenv('SWAGGER_HOST','192.168.235.130')
SWAGGER_PORT = int(os.getenv('SWAGGER_PORT',1237))


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'formatter': 'default',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'WARNING'
        },
        'app': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        },
    }
}
