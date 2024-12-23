# dao/store_dao.py

from dao.db_connection import get_db_connection
from sql_queries import (
    SELECT_ALL_STORE,
    SELECT_STORE_BY_GROUP,
    INSERT_STORE,
    DELETE_STORE_BY_TEXT,
    DELETE_STORE_BY_ID,
    UPDATE_STORE_BY_TEXT,
    SELECT_ID_BY_TEXT,
    UPDATE_STORE_LINE_TEXT_BY_ID,
    # Setting 表相关
    # Translations 表相关
)


def ensure_all_sequences():
    """
    确保 store、setting、translations 三个表的序列与表中的最大 id 同步。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 同步 store 表的序列
            cur.execute("SELECT setval('store_id_seq', (SELECT MAX(id) FROM store));")

            # 同步 setting 表的序列
            cur.execute("SELECT setval('setting_id_seq', (SELECT MAX(id) FROM setting));")

            # 同步 translations 表的序列
            cur.execute("SELECT setval('translations_id_seq', (SELECT MAX(id) FROM translations));")

        conn.commit()




def select_all_store():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_ALL_STORE)
            rows = cur.fetchall()
    return rows


def select_store_by_group(group_name):
    if not group_name:
        return select_all_store()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_STORE_BY_GROUP, (group_name,))
            rows = cur.fetchall()
    return rows


def insert_store(group_name, line_text):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(INSERT_STORE, (group_name, line_text))
        conn.commit()


def delete_store_by_text(line_text):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DELETE_STORE_BY_TEXT, (line_text,))
        conn.commit()


def delete_store_by_id(row_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DELETE_STORE_BY_ID, (row_id,))
        conn.commit()


def update_store_by_text(old_text, new_text):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(UPDATE_STORE_BY_TEXT, (new_text, old_text))
        conn.commit()


def select_id_by_text(line_text):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_ID_BY_TEXT, (line_text,))
            row = cur.fetchone()
    return row[0] if row else None


def update_store_line_text_by_id(row_id, new_text):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(UPDATE_STORE_LINE_TEXT_BY_ID, (new_text, row_id))
        conn.commit()
