# dao/translations_dao.py

from dao.db_connection import get_db_connection
from sql_queries import (
    SELECT_ALL_TRANSLATIONS,
    INSERT_OR_UPDATE_TRANSLATION,
    DELETE_TRANSLATION_BY_STORE_ID
)

def select_all_translations():
    """
    返回一个字典: {store_id: translated_text}
    """
    trans = {}
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_ALL_TRANSLATIONS)
            rows = cur.fetchall()  # [(store_id, translated_text), ...]
    for (sid, ttext) in rows:
        trans[sid] = ttext
    return trans

def upsert_translation(store_id, translated_text):
    """
    插入或更新 translations 表。store_id 唯一关联一条翻译。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(INSERT_OR_UPDATE_TRANSLATION, (store_id, translated_text))
        conn.commit()

def delete_translation(store_id):
    """
    删除指定 store_id 的翻译记录。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DELETE_TRANSLATION_BY_STORE_ID, (store_id,))
        conn.commit()
