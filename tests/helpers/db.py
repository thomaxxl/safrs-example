import logging

import psycopg2

from flask import current_app

logger = logging.getLogger(__name__)


def connect_db(db_name=None):
    con = psycopg2.connect(
        host=current_app.config["DB_HOST"],
        dbname=db_name or current_app.config["DB_NAME"],
        user=current_app.config["DB_USER"],
        password=current_app.config["DB_PWD"],
    )
    con.autocommit = True
    return con


def create_database(db_name):
    con = connect_db("postgres")
    try:
        # Create database
        con.cursor().execute(f'CREATE DATABASE "{db_name}"')
    except psycopg2.ProgrammingError as e:
        if e.pgcode == "42P04":
            # DB exists
            pass
    finally:
        con.close()

    # Create a separate connection to the new DB to create extensions
    con = connect_db(db_name)
    try:
        con.cursor().execute(f'CREATE EXTENSION "uuid-ossp"')
    except psycopg2.ProgrammingError as e:
        if e.pgcode == "42710":
            # Extension exists
            pass
    con.close()


def clean_database(db_name, schema_name="public"):
    """Drop and re-create schema"""
    try:
        con = connect_db(db_name)
    except psycopg2.OperationalError:
        # Probably doesn't exist, which is fine
        return

    try:
        cur = con.cursor()
        cur.execute(f'DROP SCHEMA if exists "{schema_name}" cascade')
        cur.execute(f"CREATE schema {schema_name}")
    except psycopg2.ProgrammingError as e:
        if e.pgcode == "3D000":
            # DB doesnt exist
            pass
    finally:
        con.close()
