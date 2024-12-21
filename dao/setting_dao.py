# dao/setting_dao.py

import json
from dao.db_connection import get_db_connection
from sql_queries import (
    UPSERT_SETTING,
    SELECT_SETTING_BY_NAME
)

def get_setting(name):
    """
    读取表中 name 对应的 selected_groups,
    并返回解析后的列表(若为空或不存在则返回空列表)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_SETTING_BY_NAME, (name,))
            row = cur.fetchone()
    if row and row[0]:
        # 假设存储为JSON字符串
        try:
            return json.loads(row[0])
        except:
            # 若不是JSON就用逗号分隔
            return row[0].split(',')
    return []

def set_setting(name, groups):
    """
    将 groups(list[str]) 存为JSON字符串插入/更新 setting 表
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            json_str = json.dumps(groups)  # 转JSON
            cur.execute(UPSERT_SETTING, (name, json_str))
        conn.commit()
