# edit_file.py

import math
from collections import defaultdict

from flask import Blueprint, render_template, request, redirect, url_for, flash

edit_file_blueprint = Blueprint('edit_file', __name__, template_folder='templates')

from services.edit_file_service import (
    load_translations,
    read_all_store,
    insert_new_lines,
    remove_line_by_id,
    update_line_text_by_id,
)
from dao.setting_dao import (
    select_setting_by_name,
    upsert_setting
)
from dao.group_dao import (
    get_all_groups,
    get_or_create_group_id
)

@edit_file_blueprint.route('/edit', methods=['GET', 'POST'])
def edit():
    """
    /file/edit 路由:
    1. 从前端 URL 或 POST 数据里解析 selected_groups / combined_training_groups (均为 group_id 列表)；
    2. 根据 action(add/delete/delete_selected/update) 对 store/translations 操作；
    3. 提供搜索 & 分页功能；
    4. 最终渲染 edit.html。
    """

    # 1. 获取前端传来的 group_id 列表
    selected_group_ids = request.args.getlist('groups', type=int)
    combined_training_ids = request.args.getlist('combined_training_groups', type=int)

    # 若 POST，则继续从 form 里获取
    if request.method == 'POST':
        posted_groups = request.form.getlist('groups')
        posted_combined = request.form.getlist('combined_training_groups')
        if posted_groups:
            selected_group_ids = [int(g) for g in posted_groups if g.isdigit()]
        if posted_combined:
            combined_training_ids = [int(c) for c in posted_combined if c.isdigit()]

    # 若未选，则尝试读 setting 表
    if not selected_group_ids:
        default_edit_choose = select_setting_by_name('edit_choose')  # list[int]
        if default_edit_choose:
            selected_group_ids = default_edit_choose
    if not combined_training_ids:
        default_combined = select_setting_by_name('combined_training')
        if default_combined:
            combined_training_ids = default_combined

    # 2. 读取全部 store 数据 + 翻译
    store_rows = read_all_store()  # [(store_id, group_id, line_text), ...]
    translations_map = load_translations()  # {store_id: translated_text}

    # 分组映射: group_id -> [(store_id, line_text), ...]
    group_map = defaultdict(list)
    for (sid, gid, txt) in store_rows:
        group_map[gid].append((sid, txt))

    # 全部分组: [(group_id, group_name), ...]
    all_groups = get_all_groups()

    # 3. 处理 POST
    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'add':
            new_line = request.form.get('new_line', '')
            new_line_translation = request.form.get('new_line_translation', '')
            new_group_name = request.form.get('new_group', '').strip()
            existing_group_str = request.form.get('existing_group', '')

            # 拆分多行
            new_lines = [x.strip() for x in new_line.split('\n') if x.strip()]
            new_trans_lines = [x.strip() for x in new_line_translation.split('\n') if x.strip()]

            # 确定最终的 group_id
            if new_group_name:
                # 新建/或获取
                group_id = get_or_create_group_id(new_group_name)
            else:
                # 使用已有组
                try:
                    group_id = int(existing_group_str)
                except:
                    group_id = None

            if not group_id:
                flash('无效组ID或组名，请检查。', 'error')
            else:
                # 插入store+translations
                if new_lines:
                    insert_new_lines(new_lines, new_trans_lines, group_id)
                    # 更新 setting('edit_choose')
                    current_edit = select_setting_by_name('edit_choose')
                    if group_id not in current_edit:
                        current_edit.append(group_id)
                        upsert_setting('edit_choose', current_edit)
                    flash('新增成功', 'success')
                else:
                    flash('没有可添加的行内容。', 'error')

        elif action == 'delete':
            row_id_str = request.form.get('row_id', '')
            try:
                rid = int(row_id_str)
                remove_line_by_id(rid)
                flash(f'已删除 store_id={rid}', 'success')
            except:
                flash('删除失败，store_id无效', 'error')

        elif action == 'delete_selected':
            selected_lines = request.form.getlist('selected_lines')
            count = 0
            for s in selected_lines:
                try:
                    rid = int(s)
                    remove_line_by_id(rid)
                    count += 1
                except:
                    pass
            flash(f'批量删除 {count} 行', 'success')

        elif action == 'update':
            row_id_str = request.form.get('row_id', '')
            updated_text = request.form.get('updated_text', '').strip()
            updated_translation = request.form.get('updated_translation', '').strip()
            try:
                row_id = int(row_id_str)
                if updated_text:
                    update_line_text_by_id(row_id, updated_text, updated_translation)
                    flash(f'更新成功 (store_id={row_id})', 'success')
                else:
                    flash('更新文本不能为空。', 'error')
            except:
                flash('更新失败, store_id无效', 'error')

        # 操作完成后, 重定向到 GET
        current_page = request.args.get('page', '1')
        search_query = request.args.get('search', '').strip()
        return redirect(url_for('edit_file.edit',
                                page=current_page,
                                search=search_query,
                                groups=selected_group_ids,
                                combined_training_groups=combined_training_ids))

    # 4. 处理 GET => 搜索 & 分页
    search_query = request.args.get('search', '').strip()
    try:
        current_page = int(request.args.get('page', '1'))
        if current_page < 1:
            current_page = 1
    except:
        current_page = 1

    # 先按选中的 group_ids 过滤
    if selected_group_ids:
        combined_rows = []
        for gid in selected_group_ids:
            combined_rows.extend(group_map[gid])
        # 去重
        tmp_dict = {}
        for (sid, txt) in combined_rows:
            tmp_dict[sid] = txt
        filtered_rows = [(k, tmp_dict[k]) for k in tmp_dict]
    else:
        # 没选 => 全部
        filtered_rows = [(r[0], r[2]) for r in store_rows]

    # 搜索
    if search_query:
        final_rows = []
        sq = search_query.lower()
        for (sid, txt) in filtered_rows:
            if sq in txt.lower():
                final_rows.append((sid, txt))
    else:
        final_rows = filtered_rows

    # 分页
    per_page = 4
    total_count = len(final_rows)
    total_pages = max(1, math.ceil(total_count / per_page))
    if current_page > total_pages:
        current_page = total_pages

    start_idx = (current_page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_rows = final_rows[start_idx:end_idx]

    # 组装 (store_id, line_text, translation)
    lines_with_translations = []
    for (sid, ltxt) in paginated_rows:
        trans = translations_map.get(sid, "")
        lines_with_translations.append((sid, ltxt, trans))

    # 注意：这里我们要把 `(group_id, group_name)` 传给模板
    # 以便模板中: {% for grp_id, grp_name in group_names %}
    return render_template(
        'edit.html',
        lines=lines_with_translations,
        current_page=current_page,
        total_pages=total_pages,
        search_query=search_query,
        # 这里直接把 all_groups (list of (id,name)) 传给模板
        group_names=all_groups,
        selected_groups=selected_group_ids,
        combined_training_groups=combined_training_ids
    )
