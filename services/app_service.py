# services/app_service.py

import hashlib
import os
import random
import re
import threading

from dao.store_dao import select_store_by_group_id
from dao.translations_dao import select_all_translations

AUDIO_PERSISTENT_DIR = 'audio_files'
translations_lock = threading.Lock()

def load_translations_from_db():
    return select_all_translations()

def get_audio_file_path(text):
    """
    根据文本生成对应的音频文件名和完整路径。
    text -> hash -> audio_xxx.mp3
    """
    text_clean = re.sub(r'<\\w+:\\s*[^>]+>', '', text)
    text_hash = hashlib.sha256(text_clean.encode('utf-8')).hexdigest()
    filename = f"audio_{text_hash}.mp3"
    file_path = os.path.join(AUDIO_PERSISTENT_DIR, filename)
    return filename, file_path

def read_text_file_by_group_id(group_id):
    """
    根据 group_id 查询 store，并返回 [line_text, ...]
    """
    rows = select_store_by_group_id(group_id)
    # rows: [(store_id, group_id, line_text), ...]
    return [r[2] for r in rows]

def shuffle_random_order(start_index, line_count):
    """
    用于随机打乱索引顺序，保证 start_index 在首位
    """
    indices = list(range(line_count))
    if start_index in indices:
        indices.remove(start_index)
    random.shuffle(indices)
    return [start_index] + indices
