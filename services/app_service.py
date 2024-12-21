# services/app_service.py

import hashlib
import os
import random
import re
import threading

from dao.store_dao import (
    select_store_by_group
)
from dao.translations_dao import select_all_translations

AUDIO_PERSISTENT_DIR = 'audio_files'
translations_lock = threading.Lock()

def load_translations_from_db():
    return select_all_translations()

def get_audio_file_path(text):
    text_clean = re.sub(r'<\\w+:\\s*[^>]+>', '', text)
    text_hash = hashlib.sha256(text_clean.encode('utf-8')).hexdigest()
    filename = f"audio_{text_hash}.mp3"
    file_path = os.path.join(AUDIO_PERSISTENT_DIR, filename)
    return filename, file_path

def read_text_file_by_group(group_name):
    rows = select_store_by_group(group_name)
    # rows: [(id, group_name, line_text), ...]
    return [r[2] for r in rows]

def shuffle_random_order(start_index, line_count):
    indices = list(range(line_count))
    if start_index in indices:
        indices.remove(start_index)
    random.shuffle(indices)
    return [start_index] + indices
