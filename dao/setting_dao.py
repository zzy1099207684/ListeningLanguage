# dao/setting_dao.py

import json
from dao.db_connection import get_db_connection
from sql_queries import (
    UPSERT_SETTING,
    SELECT_SETTING_BY_NAME
)

def get_setting(setting_name):
    """
    读取 setting 表中 setting_name 对应的 group_ids，
    并返回解析后的列表(若为空或不存在则返回空列表)。
    注意：这里存储的是一组 group_id 的列表，而非 group_name。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_SETTING_BY_NAME, (setting_name,))
            row = cur.fetchone()
    if row and row[0]:
        try:
            return json.loads(row[0])  # list of group_ids
        except:
            return []
    return []


def set_setting(setting_name, group_id_list):
    """
    将 group_id_list (list[int]) 存为JSON字符串插入/更新 setting 表
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            json_str = json.dumps(group_id_list)
            cur.execute(UPSERT_SETTING, (setting_name, json_str))
        conn.commit()


def select_setting_by_name(setting_name):
    """
    返回指定 setting_name 的 group_ids 列表（反序列化后）。
    """
    return get_setting(setting_name)


def upsert_setting(setting_name, group_id_list):
    """
    插入或更新 setting 表中的 group_ids。
    group_id_list 应为一个整数列表。
    """
    set_setting(setting_name, group_id_list)
