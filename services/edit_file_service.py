# services/edit_file_service.py

import hashlib
import os
from dao.store_dao import (
    select_all_store,
    insert_store,
    delete_store_by_text,
    update_store_by_text,
    select_id_by_text,
    delete_store_by_id,                  # 新增
    update_store_line_text_by_id         # 新增
)
from dao.translations_dao import (
    select_all_translations,
    upsert_translation,
    delete_translation
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


def insert_new_lines(new_lines, group_name=''):
    """
    新增插入时，带上指定的group_name
    """
    for nl in new_lines:
        insert_store(group_name, nl)


def remove_line_by_text(text):
    """
    原逻辑：通过文本删除。
    一旦多个行的 line_text 相同，会全部被删。
    同时删除对应翻译 & 音频。
    """
    delete_audio_file(text)
    delete_translation(text)
    delete_store_by_text(text)


def update_line_text(old_text, new_text, new_trans):
    """
    原逻辑：通过文本更新，只更新首个匹配到的行。
    """
    update_store_by_text(old_text, new_text)
    delete_audio_file(old_text)
    delete_translation(old_text)
    save_translations(new_text, new_trans)


def delete_audio_file(text):
    text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    filename = f'audio_{text_hash}.mp3'
    file_path = os.path.join(AUDIO_PERSISTENT_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)


# ================== 新增 ID 级别更新/删除逻辑 ==================

def remove_line_by_id(row_id):
    """
    新增：通过 ID 删除行；
         由于旧 remove_line_by_text() 会删除对应翻译和音频，这里调用前先查出旧文本，再复用。
    """
    from dao.db_connection import get_db_connection
    old_text = None
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT line_text FROM store WHERE id = %s LIMIT 1", (row_id,))
            row = cur.fetchone()
            if row:
                old_text = row[0]
    if old_text:
        remove_line_by_text(old_text)
    # 最后按 ID 删除 store 表记录
    delete_store_by_id(row_id)


def update_line_text_by_id(row_id, new_text, new_trans):
    """
    新增：通过 ID 更新行；
         由于旧 update_line_text() 会同时删除旧翻译及音频，这里也要先获取旧文本再复用。
    """
    from dao.db_connection import get_db_connection
    old_text = None
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT line_text FROM store WHERE id = %s LIMIT 1", (row_id,))
            row = cur.fetchone()
            if row:
                old_text = row[0]
    if old_text:
        update_line_text(old_text, new_text, new_trans)
    else:
        # 如果没找到旧文本，直接更新存储表；此情况一般不会出现
        update_store_line_text_by_id(row_id, new_text)
        delete_audio_file(new_text)  # 避免重复
        delete_translation(new_text)
        save_translations(new_text, new_trans)
