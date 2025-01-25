# dao/store_dao.py

from dao.db_connection import get_db_connection
from sql_queries import (
    SELECT_ALL_STORE,
    SELECT_STORE_BY_GROUP_ID,
    INSERT_STORE,
    DELETE_STORE_BY_ID,
    UPDATE_STORE_BY_ID,
    SELECT_STORE_BY_ID
)

def ensure_all_sequences():
    """
    确保各表的序列与表中的最大ID同步。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT setval('groups_group_id_seq', COALESCE((SELECT MAX(group_id) FROM groups), 0) + 1, false);")
            cur.execute("SELECT setval('store_store_id_seq', COALESCE((SELECT MAX(store_id) FROM store), 0) + 1, false);")
            cur.execute("SELECT setval('translations_translation_id_seq', COALESCE((SELECT MAX(translation_id) FROM translations), 0) + 1, false);")
            cur.execute("SELECT setval('setting_setting_id_seq', COALESCE((SELECT MAX(setting_id) FROM setting), 0) + 1, false);")
        conn.commit()


def select_all_store():
    """
    返回所有 store 记录: [(store_id, group_id, line_text), ...]
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_ALL_STORE)
            rows = cur.fetchall()
    return rows


def select_store_by_group_id(group_id):
    """
    返回指定 group_id 下的所有 store 行: [(store_id, group_id, line_text), ...]
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_STORE_BY_GROUP_ID, (group_id,))
            rows = cur.fetchall()
    return rows


def insert_store(group_id, line_text):
    """
    插入一条 store 记录，返回新插入的 store_id。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(INSERT_STORE, (group_id, line_text))
            new_id = cur.fetchone()[0]
        conn.commit()
    return new_id


def delete_store_by_id(store_id):
    """
    通过 store_id 删除对应记录。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DELETE_STORE_BY_ID, (store_id,))
        conn.commit()


def update_store_by_id(store_id, new_text):
    """
    更新指定 store_id 的 line_text。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(UPDATE_STORE_BY_ID, (new_text, store_id))
        conn.commit()


def select_store_by_id(store_id):
    """
    返回 (store_id, group_id, line_text) 或 None。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_STORE_BY_ID, (store_id,))
            row = cur.fetchone()
    return row
