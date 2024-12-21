# edit_file.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import math
import os
import hashlib
import json
import threading

edit_file_blueprint = Blueprint('edit_file', __name__, template_folder='templates')

TEXT_FILE_PATH = 'store.txt'
AUDIO_PERSISTENT_DIR = 'audio_files'
TRANSLATIONS_FILE_PATH = 'translations.json'
translations_lock = threading.Lock()

def read_text_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    # **修改**：跳过空行
    return [line.strip() for line in lines if line.strip()]

#####################################
# 新增：分组解析
#####################################
def parse_store_file(file_path):
    if not os.path.exists(file_path):
        return {}
    groups = {}
    current_group_name = None
    current_lines = []

    with open(file_path, 'r', encoding='utf-8') as f:
        raw_lines = [l.rstrip('\n') for l in f]

    def flush_group(gname, glines):
        if gname and glines:
            filtered = [x.strip() for x in glines if x.strip()]
            if filtered:
                groups[gname] = filtered

    for line in raw_lines:
        if not line.strip():
            flush_group(current_group_name, current_lines)
            current_group_name = None
            current_lines = []
        else:
            if current_group_name is None:
                current_group_name = line.strip()
            else:
                current_lines.append(line)

    flush_group(current_group_name, current_lines)
    return groups
#####################################


def write_text_file(file_path, lines):
    with open(file_path, 'w', encoding='utf-8') as file:
        for line in lines:
            file.write(f"{line}\n")

def delete_audio_file(text):
    text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    filename = f'audio_{text_hash}.mp3'
    file_path = os.path.join(AUDIO_PERSISTENT_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)

def load_translations():
    if os.path.exists(TRANSLATIONS_FILE_PATH):
        with open(TRANSLATIONS_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {}

def save_translations(translations):
    with open(TRANSLATIONS_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(translations, f, ensure_ascii=False, indent=4)

def delete_translation(text):
    with translations_lock:
        translations = load_translations()
        if text in translations:
            del translations[text]
            save_translations(translations)

@edit_file_blueprint.route('/edit', methods=['GET', 'POST'])
def edit():
    lines = read_text_file(TEXT_FILE_PATH)
    translations = load_translations()
    current_page = request.args.get('page', '1')
    search_query = request.args.get('search', '').strip()

    # 新增：解析组并获取所有组名
    group_map = parse_store_file(TEXT_FILE_PATH)
    all_group_names = list(group_map.keys())
    # 获取多选选中的组
    selected_groups = request.args.getlist('groups')

    try:
        current_page = int(current_page)
        if current_page < 1:
            current_page = 1
    except ValueError:
        current_page = 1

    # 若选中若干组，则只展示这些组下的内容
    grouped_lines = []
    if selected_groups:
        for g in selected_groups:
            grouped_lines.extend(group_map.get(g, []))
        # 去重
        grouped_lines = list(dict.fromkeys(grouped_lines))
        # 这里将所选组的内容与原本 lines 做一次交集（考虑旧代码中行号的对应）
        filtered_lines_by_group = [l for l in lines if l in grouped_lines]
    else:
        filtered_lines_by_group = lines

    # 然后再对它们做搜索过滤
    if search_query:
        filtered_lines = [line for line in filtered_lines_by_group if search_query.lower() in line.lower()]
    else:
        filtered_lines = filtered_lines_by_group

    per_page = 4
    total_pages = math.ceil(len(filtered_lines) / per_page) if per_page else 1
    if current_page > total_pages and total_pages != 0:
        current_page = total_pages
    start = (current_page - 1) * per_page
    end = start + per_page
    paginated_lines = filtered_lines[start:end]

    # Prepare lines with translations
    lines_with_translations = []
    for line in paginated_lines:
        translation = translations.get(line, "")
        lines_with_translations.append((line, translation))

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            new_lines = request.form.get('new_line', '').split('\n')
            new_lines = [line.strip() for line in new_lines if line.strip()]
            if new_lines:
                lines.extend(new_lines)
                write_text_file(TEXT_FILE_PATH, lines)
                flash('新行已添加。', 'success')
            else:
                flash('没有添加任何新行。', 'error')
        elif action == 'delete':
            line_number = request.form.get('line_number')
            try:
                line_number = int(line_number)
                if 0 < line_number <= len(lines):
                    text = lines[line_number - 1]
                    del lines[line_number - 1]
                    write_text_file(TEXT_FILE_PATH, lines)
                    delete_audio_file(text)
                    delete_translation(text)
                    flash(f'第 {line_number} 行已删除。', 'success')
                else:
                    flash('行号无效。', 'error')
            except (ValueError, TypeError):
                flash('行号无效。', 'error')
        elif action == 'delete_selected':
            selected_lines = request.form.getlist('selected_lines')
            texts_to_delete = []
            try:
                selected_lines = sorted(map(int, selected_lines), reverse=True)
                for line_number in selected_lines:
                    if 0 < line_number <= len(lines):
                        text = lines[line_number - 1]
                        texts_to_delete.append(text)
                        del lines[line_number - 1]
                write_text_file(TEXT_FILE_PATH, lines)
                for text in texts_to_delete:
                    delete_audio_file(text)
                    delete_translation(text)
                flash(f'{len(texts_to_delete)} 行已删除。', 'success')
            except (ValueError, TypeError):
                flash('选择的行号无效。', 'error')
        elif action == 'update':
            line_number = request.form.get('line_number')
            updated_text = request.form.get('updated_text', '').strip()
            updated_translation = request.form.get('updated_translation', '').strip()
            try:
                line_number = int(line_number)
                if 0 < line_number <= len(lines) and updated_text:
                    old_text = lines[line_number - 1]
                    lines[line_number - 1] = updated_text
                    write_text_file(TEXT_FILE_PATH, lines)
                    delete_audio_file(old_text)
                    delete_translation(old_text)
                    with translations_lock:
                        translations = load_translations()
                        translations[updated_text] = updated_translation
                        save_translations(translations)
                    flash(f'第 {line_number} 行已更新。', 'success')
                else:
                    flash('行号或更新内容无效。', 'error')
            except (ValueError, TypeError):
                flash('行号无效。', 'error')
        return redirect(url_for('edit_file.edit', page=current_page, search=search_query, groups=selected_groups))

    return render_template('edit.html',
                           lines=lines_with_translations,
                           current_page=current_page,
                           total_pages=total_pages,
                           search_query=search_query,
                           group_names=all_group_names,
                           selected_groups=selected_groups)


