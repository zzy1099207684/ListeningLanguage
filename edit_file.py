# app.py 中已注册: app.register_blueprint(edit_file_blueprint, url_prefix='/file')

import math
from collections import defaultdict

from flask import Blueprint, render_template, request, redirect, url_for, flash

edit_file_blueprint = Blueprint('edit_file', __name__, template_folder='templates')

from services.edit_file_service import (
    load_translations,
    read_all_store,
    insert_new_lines,
    remove_line_by_text,
    update_line_text,
    # 新增
    remove_line_by_id,
    update_line_text_by_id
)

from dao.db_connection import get_db_connection
from sql_queries import SELECT_SETTING_BY_NAME

import json

def get_default_groups(name='edit_choose'):
    """从 setting 表里获取 name 对应的分组列表"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_SETTING_BY_NAME, (name,))
            row = cur.fetchone()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except:
            return []
    return []


@edit_file_blueprint.route('/edit', methods=['GET', 'POST'])
def edit():
    # ---------------------------------------------------------
    # 1. 读取或合并 前端传来的 groups 参数(兼容GET/POST)
    # ---------------------------------------------------------
    selected_groups = request.args.getlist('groups', type=str)

    if request.method == 'POST':
        posted_groups = request.form.getlist('groups')
        if posted_groups:
            selected_groups = posted_groups

    if not selected_groups:
        default_groups = get_default_groups(name='edit_choose')
        if default_groups:
            selected_groups = default_groups

    rows = read_all_store()  # [(id, group_name, line_text), ...]
    translations = load_translations()

    # 构建 {group_name: [ (id, line_text), ...]} 方便按分组筛选
    group_map = defaultdict(list)
    for sid, gname, ltext in rows:
        g = gname if gname else ""
        group_map[g].append((sid, ltext))

    all_group_names = list(group_map.keys())

    # ---------------------------------------------------------
    # 2. 处理 POST 请求(新增/删除/更新)
    # ---------------------------------------------------------
    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'add':
            new_line = request.form.get('new_line', '')
            new_group = request.form.get('new_group', '').strip()
            new_lines = new_line.split('\n')
            new_lines = [x.strip() for x in new_lines if x.strip()]

            if new_lines:
                insert_new_lines(new_lines, new_group)
                flash('新行已添加。', 'success')
            else:
                flash('没有添加任何新行。', 'error')

        elif action == 'delete':
            # 改为按 row_id 删除
            row_id_str = request.form.get('row_id', '')
            try:
                row_id = int(row_id_str)
                remove_line_by_id(row_id)
                flash(f'ID={row_id} 已删除。', 'success')
            except (ValueError, TypeError):
                flash('无效ID。', 'error')

        elif action == 'delete_selected':
            selected_lines_req = request.form.getlist('selected_lines')
            success_count = 0
            for rid_str in selected_lines_req:
                try:
                    rid = int(rid_str)
                    remove_line_by_id(rid)
                    success_count += 1
                except:
                    pass
            flash(f'批量删除成功 {success_count} 行。', 'success')

        elif action == 'update':
            row_id_str = request.form.get('row_id', '')
            updated_text = request.form.get('updated_text', '').strip()
            updated_translation = request.form.get('updated_translation', '').strip()
            try:
                row_id = int(row_id_str)
                if updated_text:
                    update_line_text_by_id(row_id, updated_text, updated_translation)
                    flash(f'ID={row_id} 行已更新。', 'success')
                else:
                    flash('更新文本不能为空。', 'error')
            except (ValueError, TypeError):
                flash('无效ID。', 'error')

        current_page = request.args.get('page', '1')
        search_query = request.args.get('search', '').strip()
        return redirect(url_for('edit_file.edit', page=current_page, search=search_query, groups=selected_groups))

    # ---------------------------------------------------------
    # 3. 处理 GET 请求(过滤 & 分页)
    # ---------------------------------------------------------
    search_query = request.args.get('search', '').strip()
    try:
        current_page = int(request.args.get('page', '1'))
        if current_page < 1:
            current_page = 1
    except ValueError:
        current_page = 1

    # 先把所有行整合
    filtered_rows = []
    if selected_groups:
        # 有勾选分组
        all_rows_in_group = []
        for g in selected_groups:
            if g in group_map:
                all_rows_in_group.extend(group_map[g])
        # all_rows_in_group: [(id, line_text), ...] 可能有重复ID吗? 正常不会
        # 去重+原顺序：此处可根据项目需求来定
        # 这里简单处理：转dict后再转回list
        unique_dict = {}
        for (sid, ltext) in all_rows_in_group:
            unique_dict[sid] = ltext
        rows_in_group = [(sid, unique_dict[sid]) for sid in unique_dict.keys()]
    else:
        # 没选分组 => rows 全部
        rows_in_group = [(r[0], r[2]) for r in rows]

    # 再根据搜索关键字过滤
    if search_query:
        for (sid, ltext) in rows_in_group:
            if search_query.lower() in ltext.lower():
                filtered_rows.append((sid, ltext))
    else:
        filtered_rows = rows_in_group

    # 分页
    per_page = 4
    total_count = len(filtered_rows)
    total_pages = max(1, math.ceil(total_count / per_page))

    if current_page > total_pages and total_pages != 0:
        current_page = total_pages

    start_idx = (current_page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_rows = filtered_rows[start_idx:end_idx]

    # 构建 lines_with_translations
    lines_with_translations = []
    for (sid, ltext) in paginated_rows:
        tran = translations.get(ltext, "")
        lines_with_translations.append((sid, ltext, tran))

    # ---------------------------------------------------------
    # 4. 渲染模板
    # ---------------------------------------------------------
    return render_template(
        'edit.html',
        lines=lines_with_translations,
        current_page=current_page,
        total_pages=total_pages,
        search_query=search_query,
        group_names=all_group_names,
        selected_groups=selected_groups
    )
