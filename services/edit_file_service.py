import hashlib
import os
from dao.store_dao import (
    select_all_store,
    insert_store,
    delete_store_by_text,
    update_store_by_text
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
    delete_store_by_text(text)


def update_line_text(old_text, new_text, new_trans):
    # 先更新 store
    update_store_by_text(old_text, new_text)
    # 再删旧音频 + 旧翻译
    delete_audio_file(old_text)
    delete_translation(old_text)
    # 若需要新翻译，则插入/更新
    save_translations(new_text, new_trans)


def delete_audio_file(text):
    text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    filename = f'audio_{text_hash}.mp3'
    file_path = os.path.join(AUDIO_PERSISTENT_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
