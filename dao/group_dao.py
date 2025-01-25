# dao/group_dao.py

from dao.db_connection import get_db_connection
from sql_queries import (
    SELECT_ALL_GROUPS,
    SELECT_GROUP_BY_NAME,
    INSERT_GROUP
)

def select_all_groups():
    """
    返回所有分组: [(group_id, group_name), ...]
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_ALL_GROUPS)
            rows = cur.fetchall()
    return rows

def get_group_id_by_name(group_name):
    """
    若存在该 group_name，则返回其 group_id，否则 None
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_GROUP_BY_NAME, (group_name,))
            row = cur.fetchone()
    if row:
        return row[0]
    return None

def create_group(group_name):
    """
    创建新分组并返回 group_id
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(INSERT_GROUP, (group_name,))
            new_id = cur.fetchone()[0]
        conn.commit()
    return new_id

def get_or_create_group_id(group_name):
    """
    如果 group_name 已存在，则返回其 group_id；
    否则创建后再返回。
    """
    gid = get_group_id_by_name(group_name)
    if gid is not None:
        return gid
    return create_group(group_name)

def get_all_groups():
    """
    提供给 edit_file.py 等模块使用的函数。
    内部实际上调用 select_all_groups()。
    """
    return select_all_groups()
