# services/edit_file_service.py

import hashlib
import os
from collections import defaultdict
from dao.store_dao import (
    select_all_store,
    insert_store,
    delete_store_by_id,
    update_store_by_id,
    select_store_by_id
)
from dao.translations_dao import (
    select_all_translations,
    upsert_translation,
    delete_translation
)
from dao.setting_dao import (
    select_setting_by_name,
    upsert_setting
)
from dao.group_dao import (
    get_or_create_group_id,
    select_all_groups
)

AUDIO_PERSISTENT_DIR = 'audio_files'


def load_translations():
    return select_all_translations()


def save_translations(store_id, translated_text):
    """
    对指定 store_id 进行翻译插入/更新
    """
    upsert_translation(store_id, translated_text)


def read_all_store():
    """
    查询 store 表全部行: [(store_id, group_id, line_text), ...]
    """
    return select_all_store()


def insert_new_lines(new_lines, new_trans_lines, group_id):
    """
    将若干行文本插入 store，并为每行文本写入对应翻译（若有）。
    new_lines 和 new_trans_lines 索引一一对应。
    """
    for i, nl in enumerate(new_lines):
        store_id = insert_store(group_id, nl)
        if i < len(new_trans_lines):
            save_translations(store_id, new_trans_lines[i])


def remove_line_by_id(store_id):
    """
    通过 store_id 删除行。
    同时删除对应的翻译和音频文件。
    删除后可能要更新 setting 表以移除空分组(如果该分组无任何数据)。
    """
    row = select_store_by_id(store_id)
    if not row:
        return
    _, _, old_text = row  # (store_id, group_id, line_text)

    delete_audio_file(old_text)
    delete_translation(store_id)
    delete_store_by_id(store_id)

    # 更新 setting 表
    update_settings_after_deletion()


def update_line_text_by_id(store_id, new_text, new_trans):
    """
    通过 store_id 更新行文本。
    同时更新翻译和音频文件。
    """
    row = select_store_by_id(store_id)
    if not row:
        return
    _, _, old_text = row

    # 更新 store
    update_store_by_id(store_id, new_text)

    # 删旧音频 & 旧翻译
    delete_audio_file(old_text)
    delete_translation(store_id)

    # 存新翻译
    save_translations(store_id, new_trans)

    # 更新 setting 表
    update_settings_after_deletion()


def delete_audio_file(text):
    """
    删除对应文本的音频文件。
    """
    text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    filename = f'audio_{text_hash}.mp3'
    file_path = os.path.join(AUDIO_PERSISTENT_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)


def get_line_text_by_id(store_id):
    """
    获取指定 store_id 的 line_text。
    """
    row = select_store_by_id(store_id)
    if row:
        return row[2]
    return None


def update_settings_after_deletion():
    """
    更新 setting 表中的 group_ids：
    如果某个 group_id 在 store 表中已无数据，则从所有 setting 中移除该 group_id。
    如果 store 表中无任何数据，则清空所有 setting 的 group_ids。
    """
    remaining_group_ids = get_all_remaining_group_ids()

    # 遍历需要维护的 setting_name 列表，比如 ['edit_choose', 'combined_training']，也可能有别的
    for setting_name in ['edit_choose', 'combined_training', 'index_top']:
        group_ids = select_setting_by_name(setting_name)  # list of int
        if group_ids:
            updated_list = [gid for gid in group_ids if gid in remaining_group_ids]
            # 如果 store 已空，则 updated_list 为空
            upsert_setting(setting_name, updated_list)


def get_all_remaining_group_ids():
    """
    获取 store 表中所有存在的 group_id（去重）。
    """
    store_rows = read_all_store()
    return list({row[1] for row in store_rows if row})


def update_setting_with_group_id(setting_name, group_id):
    """
    将新的 group_id 添加到指定的 setting 表的 group_ids 中（如果尚未存在）。
    """
    group_ids = select_setting_by_name(setting_name)
    if group_id not in group_ids:
        group_ids.append(group_id)
        upsert_setting(setting_name, group_ids)


def get_or_create_group_id_by_name(gname: str):
    """
    封装从 group_name -> group_id 的逻辑。
    group_name 若不存在则创建。
    """
    if not gname.strip():
        return None
    return get_or_create_group_id(gname)


def get_all_groups():
    """
    返回 [(group_id, group_name), ...]
    """
    return select_all_groups()
