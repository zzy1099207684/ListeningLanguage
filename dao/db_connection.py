# dao/db_connection.py

import psycopg2
from db_config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )
    return conn
