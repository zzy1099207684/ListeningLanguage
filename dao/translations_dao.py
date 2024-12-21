# dao/translations_dao.py

from dao.db_connection import get_db_connection
from sql_queries import (
    SELECT_ALL_TRANSLATIONS,
    INSERT_OR_UPDATE_TRANSLATION,
    DELETE_TRANSLATION_BY_ORIGINAL
)

def select_all_translations():
    """
    返回 {original_text: translated_text}
    """
    trans = {}
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_ALL_TRANSLATIONS)
            rows = cur.fetchall()
    for (orig, tran) in rows:
        trans[orig] = tran
    return trans

def upsert_translation(original_text, translated_text):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(INSERT_OR_UPDATE_TRANSLATION, (original_text, translated_text))
        conn.commit()

def delete_translation(original_text):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DELETE_TRANSLATION_BY_ORIGINAL, (original_text,))
        conn.commit()
