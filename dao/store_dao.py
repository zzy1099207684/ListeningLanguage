# dao/store_dao.py

import os
from dao.db_connection import get_db_connection
from sql_queries import (
    SELECT_ALL_STORE,
    SELECT_STORE_BY_GROUP,
    INSERT_STORE,
    DELETE_STORE_BY_TEXT,
    UPDATE_STORE_BY_TEXT,
    SELECT_ID_BY_TEXT,
    UPDATE_STORE_LINE_TEXT_BY_ID,

    # 新增
    SELECT_ID_BY_TEXT,
    # 下方是补充新增的SQL
    DELETE_STORE_BY_ID,
    UPDATE_STORE_LINE_TEXT_BY_ID
)


def select_all_store():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_ALL_STORE)
            rows = cur.fetchall()
    # rows: [(id, group_name, line_text), ...]
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


def update_store_by_text(old_text, new_text):
    """
    仅更新首个匹配old_text的行
    """
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


# ============== 新增的方法 ==============

def delete_store_by_id(row_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DELETE_STORE_BY_ID, (row_id,))
        conn.commit()
