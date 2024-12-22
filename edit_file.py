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

# 若你已有其他方式获取默认分组，可以替换下方 get_default_groups 函数
# 这里只是示例，示范如何从表 setting 中获取 name='edit_choose' 所对应的 groups。
# 如果你的项目中已有相关 DAO 或 Service，可直接调用，而无需重复写函数。
from dao.db_connection import get_db_connection
from sql_queries import SELECT_SETTING_BY_NAME

def get_default_groups(name='edit_choose'):
    """从 setting 表里获取 name 对应的分组列表"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_SETTING_BY_NAME, (name,))
            row = cur.fetchone()  # row 形如 (selected_groups_json,)
    if row and row[0]:
        # row[0] 通常是存储的 JSON/字符串，需要解析
        # 如果直接存的是一个数组字符串，如 ["group1","group2"]，则需要用 json.loads
        import json
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

    # 如果是 POST 请求, 并且有传入 groups, 则以 POST 为准
    if request.method == 'POST':
        posted_groups = request.form.getlist('groups')
        if posted_groups:
            selected_groups = posted_groups

    # 如果尚未指定任何分组，则尝试从 setting 表获取默认分组
    if not selected_groups:
        # 若数据库中已有默认分组，则将其作为本次查询的分组
        default_groups = get_default_groups(name='edit_choose')
        if default_groups:
            selected_groups = default_groups

    # 读取文本和翻译
    rows = read_all_store()  # [(id, group_name, line_text), ...]
    all_line_texts = [r[2] for r in rows]
    translations = load_translations()

    # 构建 {group_name: [line_text, ...]} 方便按分组筛选
    group_map = defaultdict(list)
    for sid, gname, ltext in rows:
        g = gname if gname else ""  # 若无分组则视作空字符串""
        group_map[g].append(ltext)

    # 所有存在的分组
    all_group_names = list(group_map.keys())

    # ---------------------------------------------------------
    # 2. 处理 POST 请求(新增/删除/更新)
    # ---------------------------------------------------------
    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'add':
            # 读取用户输入
            new_line = request.form.get('new_line', '')
            new_group = request.form.get('new_group', '').strip()  # 从下拉框选择的分组
            new_lines = new_line.split('\n')
            new_lines = [x.strip() for x in new_lines if x.strip()]

            if new_lines:
                # 插入到指定分组 new_group
                insert_new_lines(new_lines, new_group)
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
                # 倒序删除以避免索引混乱
                selected_lines_req = sorted(map(int, selected_lines_req), reverse=True)
                for ln in selected_lines_req:
                    if 0 < ln <= len(all_line_texts):
                        texts_to_delete.append(all_line_texts[ln - 1])
                for t in texts_to_delete:
                    remove_line_by_text(t)
                flash(f'已删除 {len(texts_to_delete)} 行。', 'success')
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

        # 处理完毕后重定向回列表页，带上当前 groups、search、page
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

    # 根据选择的分组, 筛选行
    if selected_groups:
        lines_by_group = []
        for g in selected_groups:
            # 确保该分组在 group_map 中才筛选
            if g in group_map:
                lines_by_group.extend(group_map[g])
        # 去重 & 只保留原顺序
        lines_by_group = list(dict.fromkeys(lines_by_group))
        filtered_lines_by_group = [t for t in all_line_texts if t in lines_by_group]
    else:
        # 若未选任何分组, 则默认展示所有
        filtered_lines_by_group = all_line_texts

    # 如果有搜索关键字, 进一步过滤
    if search_query:
        filtered_lines = [line for line in filtered_lines_by_group if search_query.lower() in line.lower()]
    else:
        filtered_lines = filtered_lines_by_group

    # 分页逻辑
    per_page = 4
    total_count = len(filtered_lines)
    total_pages = max(1, math.ceil(total_count / per_page))

    if current_page > total_pages and total_pages != 0:
        current_page = total_pages

    start = (current_page - 1) * per_page
    end = start + per_page
    paginated_lines = filtered_lines[start:end]

    lines_with_translations = []
    for line_text in paginated_lines:
        translation = translations.get(line_text, "")
        lines_with_translations.append((line_text, translation))

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
