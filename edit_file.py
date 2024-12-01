from flask import Blueprint, render_template, request, redirect, url_for, flash
import math
import os
import hashlib

edit_file_blueprint = Blueprint('edit_file', __name__, template_folder='templates')

TEXT_FILE_PATH = 'store.txt'
AUDIO_PERSISTENT_DIR = 'audio_files'

def read_text_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    return [line.strip() for line in lines]

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

@edit_file_blueprint.route('/edit', methods=['GET', 'POST'])
def edit():
    lines = read_text_file(TEXT_FILE_PATH)
    current_page = int(request.args.get('page', 1))
    per_page = 10
    total_pages = math.ceil(len(lines) / per_page)
    start = (current_page - 1) * per_page
    end = start + per_page
    paginated_lines = lines[start:end]

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            new_lines = request.form.get('new_line', '').split('\n')
            lines.extend([line.strip() for line in new_lines if line.strip()])
            write_text_file(TEXT_FILE_PATH, lines)
            flash('新行已添加。', 'success')
        elif action == 'delete':
            line_number = int(request.form.get('line_number'))
            if 0 < line_number <= len(lines):
                # 获取要删除的文本
                text = lines[line_number - 1]
                del lines[line_number - 1]
                write_text_file(TEXT_FILE_PATH, lines)
                # 删除对应的音频文件
                delete_audio_file(text)
                flash(f'第 {line_number} 行已删除。', 'success')
        elif action == 'delete_selected':
            selected_lines = request.form.getlist('selected_lines')
            texts_to_delete = []
            for line_number in sorted(map(int, selected_lines), reverse=True):
                if 0 < line_number <= len(lines):
                    text = lines[line_number - 1]
                    texts_to_delete.append(text)
                    del lines[line_number - 1]
            write_text_file(TEXT_FILE_PATH, lines)
            # 删除对应的音频文件
            for text in texts_to_delete:
                delete_audio_file(text)
            flash(f'{len(selected_lines)} 行已删除。', 'success')
        elif action == 'update':
            line_number = int(request.form.get('line_number'))
            updated_text = request.form.get('updated_text', '').strip()
            if 0 < line_number <= len(lines) and updated_text:
                # 获取旧的文本
                old_text = lines[line_number - 1]
                lines[line_number - 1] = updated_text
                write_text_file(TEXT_FILE_PATH, lines)
                # 删除旧的音频文件
                delete_audio_file(old_text)
                flash(f'第 {line_number} 行已更新。', 'success')
        return redirect(url_for('edit_file.edit', page=current_page))

    return render_template('edit.html',
                           lines=paginated_lines,
                           current_page=current_page,
                           total_pages=total_pages)
