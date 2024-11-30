from flask import Blueprint, render_template, request, redirect, url_for, jsonify
import os
import math

edit_file_blueprint = Blueprint('edit_file', __name__, template_folder='templates')

TEXT_FILE_PATH = 'store.txt'
LINES_PER_PAGE = 10  # 每页显示的行数

# 读取文本文件
def read_text_file(file_path):
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            pass  # 创建空文件
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    return [line.strip() for line in lines if line.strip()]

# 写入文本文件
def write_text_file(file_path, lines):
    with open(file_path, 'w', encoding='utf-8') as file:
        for line in lines:
            file.write(line + '\n')

@edit_file_blueprint.route('/edit', methods=['GET', 'POST'])
def edit():
    if request.method == 'POST':
        action = request.form.get('action')
        current_page = int(request.args.get('page', 1))
        if action == 'add':
            new_lines = request.form.get('new_line')
            if new_lines:
                lines = read_text_file(TEXT_FILE_PATH)
                # 处理多行输入，按每行一条数据添加
                for line in new_lines.splitlines():
                    line = line.strip()
                    if line:
                        lines.append(line)
                write_text_file(TEXT_FILE_PATH, lines)
        elif action == 'delete':
            line_number = int(request.form.get('line_number')) - 1
            lines = read_text_file(TEXT_FILE_PATH)
            if 0 <= line_number < len(lines):
                lines.pop(line_number)
                write_text_file(TEXT_FILE_PATH, lines)
        elif action == 'delete_selected':
            line_numbers = request.form.getlist('selected_lines')
            if line_numbers:
                lines = read_text_file(TEXT_FILE_PATH)
                # 将行号转换为索引，降序排序
                indexes = sorted([int(num) - 1 for num in line_numbers], reverse=True)
                for index in indexes:
                    if 0 <= index < len(lines):
                        lines.pop(index)
                write_text_file(TEXT_FILE_PATH, lines)
        elif action == 'update':
            line_number = int(request.form.get('line_number')) - 1
            updated_text = request.form.get('updated_text')
            lines = read_text_file(TEXT_FILE_PATH)
            if 0 <= line_number < len(lines) and updated_text:
                lines[line_number] = updated_text.strip()
                write_text_file(TEXT_FILE_PATH, lines)
        return redirect(url_for('edit_file.edit', page=current_page))

    # GET 请求，显示编辑页面并处理分页
    lines = read_text_file(TEXT_FILE_PATH)
    total_lines = len(lines)
    total_pages = math.ceil(total_lines / LINES_PER_PAGE) if LINES_PER_PAGE else 1
    try:
        current_page = int(request.args.get('page', 1))
    except ValueError:
        current_page = 1
    if current_page < 1:
        current_page = 1
    elif current_page > total_pages and total_pages != 0:
        current_page = total_pages

    start = (current_page - 1) * LINES_PER_PAGE
    end = start + LINES_PER_PAGE
    paginated_lines = lines[start:end]

    return render_template('edit.html', lines=paginated_lines, current_page=current_page, total_pages=total_pages)
