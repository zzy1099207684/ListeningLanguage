# services/edit_file_service.py

import hashlib
import os
from collections import defaultdict
from dao.store_dao import (
    select_all_store,
    insert_store,
    delete_store_by_text,
    delete_store_by_id,
    update_store_by_text,
    update_store_line_text_by_id
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

AUDIO_PERSISTENT_DIR = 'audio_files'


def load_translations():
    return select_all_translations()


def save_translations(original_text, translated_text):
    upsert_translation(original_text, translated_text)


def read_all_store():
    """
    查询 store 表全部行: [(id, group_name, line_text), ...]
    """
    return select_all_store()


def insert_new_lines(new_lines, group_name='', new_group=None):
    """
    新增插入时，带上指定的 group_name 或 new_group。
    如果 new_group 存在，优先使用它作为 group_name。
    """
    if new_group:
        group_name = new_group.strip()
    for nl in new_lines:
        insert_store(group_name, nl)
    if group_name:
        # 更新对应的 setting 表
        if new_group:
            update_setting_selected_groups('edit_choose', group_name)
        # 如果需要将新组也添加到 combined_training，可以在此处处理
        # 例如，假设有一个checkbox决定是否将新组添加到 combined_training
        # 这里假设不自动添加到 combined_training
        # 若有需求，可根据具体情况修改
        # For example:
        # if add_to_combined_training:
        #     update_setting_selected_groups('combined_training', group_name)
        pass


def remove_line_by_text(text):
    """
    通过文本删除行。
    如果删除后某个分组没有任何数据，更新 setting 表以移除该分组。
    同时删除对应的翻译和音频文件。
    """
    delete_audio_file(text)
    delete_translation(text)
    delete_store_by_text(text)
    # 更新 setting 表
    update_settings_after_deletion()


def remove_line_by_id(row_id):
    """
    通过 ID 删除行。
    如果删除后某个分组没有任何数据，更新 setting 表以移除该分组。
    同时删除对应的翻译和音频文件。
    """
    old_text = get_line_text_by_id(row_id)
    if old_text:
        delete_audio_file(old_text)
        delete_translation(old_text)
        delete_store_by_id(row_id)
        # 更新 setting 表
        update_settings_after_deletion()


def update_line_text(old_text, new_text, new_trans):
    """
    通过文本更新行，只更新首个匹配到的行。
    同时更新翻译和音频文件。
    """
    update_store_by_text(old_text, new_text)
    delete_audio_file(old_text)
    delete_translation(old_text)
    save_translations(new_text, new_trans)
    # 如果分组发生变化，可能需要更新 setting 表
    update_settings_after_deletion()


def update_line_text_by_id(row_id, new_text, new_trans):
    """
    通过 ID 更新行。
    同时更新翻译和音频文件。
    """
    old_text = get_line_text_by_id(row_id)
    if old_text:
        update_store_by_text(old_text, new_text)
        delete_audio_file(old_text)
        delete_translation(old_text)
    else:
        # 如果没有找到旧文本，直接更新
        update_store_line_text_by_id(row_id, new_text)
    save_translations(new_text, new_trans)
    # 更新 setting 表以反映可能的分组变化
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


def get_line_text_by_id(row_id):
    """
    获取指定 ID 的 line_text。
    """
    from dao.db_connection import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT line_text FROM store WHERE id = %s LIMIT 1", (row_id,))
            row = cur.fetchone()
    return row[0] if row else None


def update_settings_after_deletion():
    """
    更新 setting 表中的 selected_groups。
    如果某个分组在 store 表中已无数据，则从 selected_groups 中移除该分组。
    如果 store 表中无任何数据，则清空 selected_groups。
    """
    # 获取 store 表中所有剩余的分组
    remaining_groups = get_all_remaining_groups()

    # 获取当前 setting 表中的 selected_groups
    edit_choose_groups = select_setting_by_name('edit_choose')  # 'edit_choose' 用于 "choose group(s)"
    combined_training_groups = select_setting_by_name('combined_training')  # 'combined_training' 用于 "combined training group"

    # 过滤掉已无数据的分组
    updated_edit_choose = [g for g in edit_choose_groups if g in remaining_groups]
    updated_combined_training = [g for g in combined_training_groups if g in remaining_groups]

    # 如果没有任何分组剩余，清空 selected_groups
    if not remaining_groups:
        updated_edit_choose = []
        updated_combined_training = []

    # 更新 setting 表
    upsert_setting('edit_choose', updated_edit_choose)
    upsert_setting('combined_training', updated_combined_training)


def get_all_remaining_groups():
    """
    获取 store 表中所有存在的分组。
    """
    store_rows = read_all_store()
    group_set = set()
    for row in store_rows:
        group_name = row[1] if row[1] else ""
        if group_name:
            group_set.add(group_name)
    return list(group_set)


def update_setting_selected_groups(setting_name, new_group):
    """
    将新的组名添加到指定的 setting 表的 selected_groups 中（如果尚未存在）。
    """
    selected_groups = select_setting_by_name(setting_name)
    if new_group and new_group not in selected_groups:
        selected_groups.append(new_group)
        upsert_setting(setting_name, selected_groups)
