# edit_file.py

import math
from collections import defaultdict

from flask import Blueprint, render_template, request, redirect, url_for, flash

edit_file_blueprint = Blueprint('edit_file', __name__, template_folder='templates')

from services.edit_file_service import (
    load_translations,
    read_all_store,
    insert_new_lines,
    remove_line_by_text,
    update_line_text
)

@edit_file_blueprint.route('/edit', methods=['GET', 'POST'])
def edit():
    # 读取数据库 store
    rows = read_all_store()  # [(id, group_name, line_text), ...]
    all_line_texts = [r[2] for r in rows]  # 仅取 line_text

    translations = load_translations()
    current_page = request.args.get('page', '1')
    search_query = request.args.get('search', '').strip()

    # 构建 {group_name: [line_text, ...]}
    group_map = defaultdict(list)
    for (sid, gname, ltext) in rows:
        group_map[gname if gname else ""].append(ltext)
    all_group_names = list(group_map.keys())

    selected_groups = request.args.getlist('groups')
    try:
        current_page = int(current_page)
        if current_page < 1:
            current_page = 1
    except ValueError:
        current_page = 1

    # 筛选组
    if selected_groups:
        lines_by_group = []
        for g in selected_groups:
            lines_by_group.extend(group_map[g])
        lines_by_group = list(dict.fromkeys(lines_by_group))
        filtered_lines_by_group = [t for t in all_line_texts if t in lines_by_group]
    else:
        filtered_lines_by_group = all_line_texts

    # 搜索过滤
    if search_query:
        filtered_lines = [line for line in filtered_lines_by_group if search_query.lower() in line.lower()]
    else:
        filtered_lines = filtered_lines_by_group

    per_page = 4
    total_pages = max(1, math.ceil(len(filtered_lines) / per_page))
    if current_page > total_pages and total_pages != 0:
        current_page = total_pages
    start = (current_page - 1) * per_page
    end = start + per_page
    paginated_lines = filtered_lines[start:end]

    lines_with_translations = []
    for l in paginated_lines:
        translation = translations.get(l, "")
        lines_with_translations.append((l, translation))

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            new_line = request.form.get('new_line', '')
            new_lines = new_line.split('\n')
            new_lines = [x.strip() for x in new_lines if x.strip()]
            if new_lines:
                insert_new_lines(new_lines)
                flash('新行已添加。', 'success')
            else:
                flash('没有添加任何新行。', 'error')

        elif action == 'delete':
            line_number = request.form.get('line_number')
            try:
                line_number = int(line_number)
                if 0 < line_number <= len(all_line_texts):
                    text = all_line_texts[line_number - 1]
                    remove_line_by_text(text)
                    flash(f'第 {line_number} 行已删除。', 'success')
                else:
                    flash('行号无效。', 'error')
            except (ValueError, TypeError):
                flash('行号无效。', 'error')

        elif action == 'delete_selected':
            selected_lines_req = request.form.getlist('selected_lines')
            texts_to_delete = []
            try:
                selected_lines_req = sorted(map(int, selected_lines_req), reverse=True)
                for ln in selected_lines_req:
                    if 0 < ln <= len(all_line_texts):
                        texts_to_delete.append(all_line_texts[ln - 1])
                for t in texts_to_delete:
                    remove_line_by_text(t)
                flash(f'{len(texts_to_delete)} 行已删除。', 'success')
            except (ValueError, TypeError):
                flash('选择的行号无效。', 'error')

        elif action == 'update':
            line_number = request.form.get('line_number')
            updated_text = request.form.get('updated_text', '').strip()
            updated_translation = request.form.get('updated_translation', '').strip()
            try:
                line_number = int(line_number)
                if 0 < line_number <= len(all_line_texts) and updated_text:
                    old_text = all_line_texts[line_number - 1]
                    update_line_text(old_text, updated_text, updated_translation)
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
