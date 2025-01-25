import atexit
import hashlib
import os
import random
import re
import tempfile
import threading

from deep_translator import GoogleTranslator
from flask import Flask, render_template, request, jsonify, send_from_directory, session, Response, redirect, url_for
from flask_session import Session
from gtts import gTTS

# dao
from dao.store_dao import select_all_store, select_store_by_group_id, ensure_all_sequences
from dao.translations_dao import select_all_translations, delete_translation, upsert_translation
from dao.setting_dao import get_setting, set_setting
from dao.group_dao import select_all_groups
from services.app_service import (
    get_audio_file_path,
    shuffle_random_order
)
# 蓝图: edit_file
from edit_file import edit_file_blueprint

app = Flask(__name__)
app.register_blueprint(edit_file_blueprint, url_prefix='/file')

# session 配置
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(tempfile.gettempdir(), 'flask_sessions')
app.config['SESSION_PERMANENT'] = False
app.config['SECRET_KEY'] = 'safe_safe_safe'
Session(app)

AUDIO_PERSISTENT_DIR = 'audio_files'
os.makedirs(AUDIO_PERSISTENT_DIR, exist_ok=True)

translations_lock = threading.Lock()

# 程序启动时确保数据库表的序列同步
with app.app_context():
    ensure_all_sequences()


def delete_temp_files():
    pass

atexit.register(delete_temp_files)

@app.before_request
def initialize_session_vars():
    # 播放模式相关
    if 'current_index' not in session:
        session['current_index'] = 0
    if 'play_count' not in session:
        session['play_count'] = 1
    if 'play_interval' not in session:
        session['play_interval'] = 1
    if 'play_mode' not in session:
        session['play_mode'] = 'sequential'
    if 'random_order' not in session:
        session['random_order'] = []
    if 'random_index' not in session:
        session['random_index'] = 0

    # mixed_training 相关
    if 'mixed_set_initial' not in session:
        session['mixed_set_initial'] = []
    if 'mixed_set' not in session:
        session['mixed_set'] = []
    if 'last_en' not in session:
        session['last_en'] = None


@app.route('/restart', methods=['GET'])
def restart():
    os.system("sudo systemctl restart your_project_service")
    return "Project restarted successfully!", 200


@app.route('/language')
def index():
    """
    主页: 播放页面
    """
    return render_template('index.html')


################################
# get_groups / set_setting_groups
# 主要用于前端多选下拉(选中 group_id 列表) => setting
################################
@app.route('/get_groups', methods=['GET'])
def get_groups():
    """
    查询 groups 表，返回 {groups: [{id, name}, ...]}。
    前端 multipleSelect 里用 group_id 作为 value。
    """
    rows = select_all_groups()  # [(group_id, group_name)]
    data = [{'id': r[0], 'name': r[1]} for r in rows]
    return jsonify({'groups': data})


@app.route('/get_setting_groups', methods=['GET'])
def get_setting_groups():
    """
    根据 ?name=xxx，从 setting 表中获取 group_ids(list[int]) 并返回。
    """
    setting_name = request.args.get('name', '')
    if not setting_name:
        return jsonify({'status': 'error', 'message': 'missing name'})
    group_id_list = get_setting(setting_name)  # list[int]
    return jsonify({'status': 'success', 'groups': group_id_list})


@app.route('/set_setting_groups', methods=['POST'])
def set_setting_groups():
    """
    接收 JSON: {name: 'xxx', groups: [1,2,3]} => 写入 setting 表
    """
    data = request.get_json()
    name = data.get('name', '').strip()
    group_ids = data.get('groups', [])
    if not name:
        return jsonify({'status': 'error', 'message': 'invalid name'})
    if not isinstance(group_ids, list):
        return jsonify({'status': 'error', 'message': 'invalid groups'})
    set_setting(name, group_ids)
    return jsonify({'status': 'success'})


################################
# 播放逻辑
################################
def read_texts_by_group_ids(gid_list):
    """
    若 gid_list 为空 => 返回全部 store 中的 line_text
    否则只返回指定 group_id 下的 line_text
    """
    lines = []
    if not gid_list:
        # 全部
        rows = select_all_store()  # [(store_id, group_id, line_text)]
        for sid, grp, ltxt in rows:
            lines.append(ltxt)
    else:
        # 指定 group_ids
        for g in gid_list:
            rows = select_store_by_group_id(g)
            for sid, grp, ltxt in rows:
                lines.append(ltxt)
    return lines


@app.route('/play', methods=['POST'])
def play():
    """
    播放下一句逻辑:
    1. 读取 setting.index_top => group_ids
    2. 查找对应 store 行的 line_text
    3. 按 session['play_mode'] (sequential/random)
    4. 返回 (audio_url, text)
    """
    selected_groups = get_setting('index_top')  # list[int]
    current_lines = read_texts_by_group_ids(selected_groups)
    total = len(current_lines)
    if total == 0:
        return jsonify({'status': 'no_more_text'})

    if session['play_mode'] == 'sequential':
        idx = session['current_index']
        if idx >= total:
            idx = 0
            session['current_index'] = 0
        text = current_lines[idx]
        filename, file_path = get_audio_file_path(text)
        create_audio_if_not_exists(text, file_path)
        return jsonify({
            'status': 'success',
            'audio_url': f'/audio/{filename}',
            'text': text,
            'current_index': idx
        })
    else:  # random
        if not session['random_order']:
            # 初始化随机
            session['random_order'] = list(range(total))
            random.shuffle(session['random_order'])
            session['random_index'] = 0

        if session['random_index'] >= total:
            # reshuffle
            last_one = session['random_order'][-1]
            session['random_order'] = shuffle_random_order(last_one, total)
            session['random_index'] = 0

        idx_random = session['random_order'][session['random_index']]
        text = current_lines[idx_random]
        filename, file_path = get_audio_file_path(text)
        create_audio_if_not_exists(text, file_path)
        session['random_index'] += 1
        return jsonify({
            'status': 'success',
            'audio_url': f'/audio/{filename}',
            'text': text,
            'current_index': idx_random
        })


def create_audio_if_not_exists(original_text, file_path):
    """
    若音频文件不存在则生成
    """
    if os.path.exists(file_path):
        return
    # 遇 '/' => 暂做间隔
    mod_text = original_text.replace('/', ' ... ')
    tts = gTTS(text=mod_text, lang='en', tld='com')
    tts.save(file_path)


@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_PERSISTENT_DIR, filename, as_attachment=False)


@app.route('/set_play_options', methods=['POST'])
def set_play_options():
    try:
        session['play_count'] = int(request.form.get('play_count', 1))
        session['play_interval'] = int(request.form.get('play_interval', 1))
    except ValueError:
        return jsonify({'status': 'error', 'message': 'invalid input'})
    return jsonify({'status': 'options_set'})


@app.route('/get_play_options', methods=['GET'])
def get_play_options():
    return jsonify({
        'play_count': session['play_count'],
        'play_interval': session['play_interval']
    })


@app.route('/get_current_text', methods=['GET'])
def get_current_text():
    selected_groups = get_setting('index_top')  # list[int]
    lines = read_texts_by_group_ids(selected_groups)
    idx = session['current_index']
    if 0 <= idx < len(lines):
        return jsonify({
            'status': 'success',
            'text': lines[idx],
            'sentence_index': idx
        })
    else:
        return jsonify({'status': 'success', 'text': 'no more.', 'sentence_index': -1})


@app.route('/stop', methods=['POST'])
def stop():
    session['current_index'] = 0
    session['random_index'] = 0
    return jsonify({'status': 'stopped'})


@app.route('/toggle_play_mode', methods=['POST'])
def toggle_play_mode():
    selected_groups = get_setting('index_top')
    lines = read_texts_by_group_ids(selected_groups)
    total = len(lines)

    if session['play_mode'] == 'sequential':
        # 切换到随机
        session['play_mode'] = 'random'
        if total > 0:
            cur = session.get('current_index', 0)
            if cur >= total:
                cur = 0
            session['random_order'] = shuffle_random_order(cur, total)
        session['random_index'] = 0
    else:
        # 切到顺序
        session['play_mode'] = 'sequential'
    return jsonify({'status': 'mode_toggled', 'play_mode': session['play_mode']})


@app.route('/get_play_mode', methods=['GET'])
def get_play_mode():
    return jsonify({'play_mode': session['play_mode']})


@app.route('/next', methods=['POST'])
def next_line():
    selected_groups = get_setting('index_top')
    lines = read_texts_by_group_ids(selected_groups)
    total = len(lines)
    if total == 0:
        return jsonify({'status': 'no_more_text'})

    if session['play_mode'] == 'sequential':
        if session['current_index'] < total - 1:
            session['current_index'] += 1
        else:
            session['current_index'] = 0
        return jsonify({'status': 'success', 'current_index': session['current_index']})
    else:  # random
        if not session['random_order']:
            session['random_order'] = list(range(total))
            random.shuffle(session['random_order'])
            session['random_index'] = 0
        if session['random_index'] < total - 1:
            session['random_index'] += 1
        else:
            last_idx = session['random_order'][-1]
            session['random_order'] = shuffle_random_order(last_idx, total)
            session['random_index'] = 0
        return jsonify({'status': 'success', 'current_index': session['random_order'][session['random_index']]})


@app.route('/previous', methods=['POST'])
def previous_line():
    selected_groups = get_setting('index_top')
    lines = read_texts_by_group_ids(selected_groups)
    total = len(lines)
    if total == 0:
        return jsonify({'status': 'no_more_text'})

    if session['play_mode'] == 'sequential':
        if session['current_index'] > 0:
            session['current_index'] -= 1
            return jsonify({'status': 'success', 'current_index': session['current_index']})
        else:
            return jsonify({'status': 'no_previous'})
    else:
        if session['random_index'] > 0:
            session['random_index'] -= 1
            return jsonify({'status': 'success', 'current_index': session['random_order'][session['random_index']]})
        else:
            return jsonify({'status': 'no_previous'})


################################
# 翻译相关
################################
@app.route('/translate', methods=['POST'])
def translate_text():
    """
    简化逻辑：仅判断是否在 translations, 否则 missing
    (前端仅做展示用)
    """
    try:
        data = request.get_json()
        text = data.get('text', '')
        text_clean = re.sub(r'<(\w+):\s*([^>]+)>', r'\2', text)

        with translations_lock:
            all_trans = select_all_translations()  # {store_id: translated_text}
        # 由于我们没有 text->store_id 的映射过程(如果不做), 就统一返回 missing
        # 您若想做更精细的匹配, 需要在 store_dao里额外做 text->store_id 查询.
        # 这里仅保留原功能：不会报错，但会 "missing_translation".
        return jsonify({'status': 'missing_translation'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


################################
# 扫描资源(翻译 & 音频)
################################
@app.route('/scan_resources', methods=['GET'])
def scan_resources():
    """
    基于 store 表, 如果 translations 没有对应 store_id，则自动翻译
    如果音频文件不存在则生成
    """
    import json

    def generate_events():
        try:
            rows = select_all_store()  # [(store_id, group_id, line_text)]
            if not rows:
                yield f"data: {json.dumps({'status': 'done', 'message': 'no data'})}\n\n"
                return

            with translations_lock:
                current_trans = select_all_translations()  # {store_id: translated_text}

            lines_to_scan = []
            for (sid, gid, ltext) in rows:
                if sid not in current_trans:  # 需要翻译
                    lines_to_scan.append((sid, ltext))
                else:
                    # 就算已有翻译，也要检查音频文件
                    filename, file_path = get_audio_file_path(ltext)
                    create_audio_if_not_exists(ltext, file_path)

            if not lines_to_scan:
                yield f"data: {json.dumps({'status': 'done'})}\n\n"
                return

            total = len(lines_to_scan)
            for i, (store_id, text) in enumerate(lines_to_scan):
                filename, file_path = get_audio_file_path(text)
                create_audio_if_not_exists(text, file_path)
                # 翻译
                text_clean = re.sub(r'<\w+:\s*([^>]+)>', r'\1', text)
                translated_text = GoogleTranslator(source='en', target='zh-CN').translate(text_clean)
                upsert_translation(store_id, translated_text)

                progress = (i + 1) / total * 100
                data = {
                    "status": "working",
                    "progress": progress,
                    "current_index": i + 1,
                    "total": total
                }
                yield f"data: {json.dumps(data)}\n\n"

            yield f"data: {json.dumps({'status': 'done'})}\n\n"
        except Exception as e:
            err_data = {"status": "error", "message": str(e)}
            yield f"data: {json.dumps(err_data)}\n\n"

    return Response(generate_events(), mimetype='text/event-stream')


################################
# Mixed Training 相关
################################

@app.route('/mixed_training_setup', methods=['GET'])
def mixed_training_setup():
    """
    由首页按钮或 edit 页面按钮进入:
    1. 获取 setting.combined_training => group_ids
    2. 收集对应 store 行(若没有，就取全部)
    3. 做随机若干选(或全部?), 生成中英配对(从 translations), 并随机决定 en->zh / zh->en
    4. 存 session
    5. 重定向 /mixed_training
    """
    from dao.store_dao import select_store_by_group_id
    from dao.translations_dao import select_all_translations

    group_ids = get_setting('combined_training')  # list[int]
    store_rows = []

    if group_ids:
        # 收集所有
        for gid in group_ids:
            store_rows.extend(select_store_by_group_id(gid))
    else:
        # 若没设置, 读全部
        store_rows = select_all_store()

    # store_rows => [(store_id, group_id, line_text), ...]
    if not store_rows:
        # 没有数据 => 回主页
        return redirect(url_for('index'))

    # load translations => {store_id: translated_text}
    all_trans = select_all_translations()
    # 构建混合集
    # 1. 准备: 先把 store_id, text, translation
    # 2. direction: en2zh / zh2en, 并统计
    import random

    # 这里可自定义size, 也可全部
    sample_count = len(store_rows)  # or min(10, len(store_rows)) if您想一次抽10条
    chosen_rows = random.sample(store_rows, sample_count)

    # 不要一直同方向
    directions_list = []
    for i in range(sample_count):
        while True:
            cand = random.choice(['en2zh', 'zh2en'])
            if len(directions_list) >= 2 and directions_list[-1] == directions_list[-2] == cand:
                continue
            directions_list.append(cand)
            break

    mixed_set = []
    for idx, r in enumerate(chosen_rows):
        sid, g, ltext = r
        text_clean = re.sub(r'<\w+:\s*([^>]+)>', r'\1', ltext)
        zh_trans = all_trans.get(sid, '')
        if not zh_trans:
            zh_trans = "未找到翻译(请先 scan new resource)"

        direction = directions_list[idx]
        item = {
            'store_id': sid,
            'en': text_clean,  # 原文假设是英文
            'zh': zh_trans,
            'wrong_count': 0,
            'direction': direction
        }
        mixed_set.append(item)

    session['mixed_set_initial'] = [dict(m) for m in mixed_set]
    session['mixed_set'] = mixed_set
    session['last_en'] = None
    return redirect(url_for('mixed_training'))


@app.route('/mixed_training')
def mixed_training():
    """
    渲染训练页面
    """
    return render_template('mixed_training.html')


@app.route('/mixed_training_next', methods=['GET'])
def mixed_training_next():
    """
    前端JS => /mixed_training_next?super_mixed=0/1
    返回: {status, show_text, lang, audio_url, remaining_count}
    """
    super_mixed = request.args.get('super_mixed', '0')
    mixed_set = session.get('mixed_set', [])
    if not mixed_set:
        return jsonify({'status': 'done'})

    import random
    remaining_count = len(mixed_set)
    if remaining_count == 0:
        return jsonify({'status': 'done'})

    # 随机取一条: 并尽量避免与last_en重复(尝试10次)
    last_en = session.get('last_en', None)
    chosen_item = None
    for _ in range(10):
        cand = random.choice(mixed_set)
        if cand['en'] != last_en:
            chosen_item = cand
            break
    if not chosen_item:
        chosen_item = mixed_set[0]

    session['last_en'] = chosen_item['en']

    if super_mixed == '1':
        # 超混合 => 随机决定看英文还是看中文
        show_lang = random.choice(['en', 'zh'])
    else:
        # 正常 => en2zh则显示英文, zh2en则显示中文
        if chosen_item['direction'] == 'en2zh':
            show_lang = 'en'
        else:
            show_lang = 'zh'

    show_text = chosen_item[show_lang]
    # 生成音频(只对英文)
    if chosen_item['en']:
        filename, file_path = get_audio_file_path(chosen_item['en'])
        create_audio_if_not_exists(chosen_item['en'], file_path)
        audio_url = f'/audio/{filename}'
    else:
        audio_url = ''

    return jsonify({
        'status': 'success',
        'show_text': show_text,
        'lang': show_lang,
        'audio_url': audio_url,
        'remaining_count': remaining_count
    })


@app.route('/mixed_training_mark', methods=['POST'])
def mixed_training_mark():
    """
    记住/未记住 => wrong_count +=1 or remove
    并返回 found_en / found_zh
    """
    data = request.get_json()
    show_text = data.get('show_text', '').strip()
    choice = data.get('choice', '')
    lang = data.get('lang', 'en')

    mixed_set = session.get('mixed_set', [])
    found_item = None
    for item in mixed_set:
        if item[lang] == show_text:
            found_item = item
            break
    if not found_item:
        return jsonify({'status': 'error', 'message': 'not found'})

    found_en = found_item['en']
    found_zh = found_item['zh']

    if choice == 'known':
        # 记住 => 移除
        mixed_set.remove(found_item)
        session['mixed_set'] = mixed_set
        return jsonify({
            'status': 'success',
            'found_en': found_en,
            'found_zh': found_zh
        })
    elif choice == 'unknown':
        # 未记住 => wrong_count+1
        found_item['wrong_count'] += 1
        session['mixed_set'] = mixed_set
        return jsonify({
            'status': 'success',
            'found_en': found_en,
            'found_zh': found_zh
        })
    else:
        # fallback
        return jsonify({'status': 'error', 'message': 'invalid choice'})


@app.route('/mixed_training_check_finish', methods=['GET'])
def mixed_training_check_finish():
    """
    前端每次请求下一条前先检查, 若 session['mixed_set'] 已空 => finished
    """
    mixed_set = session.get('mixed_set', [])
    if not mixed_set:
        return jsonify({'status': 'finished'})
    else:
        return jsonify({'status': 'not_finished'})


@app.route('/mixed_training_all_done')
def mixed_training_all_done():
    return redirect(url_for('mixed_training_finish'))


@app.route('/mixed_training_finish')
def mixed_training_finish():
    """
    最终统计错误, 显示
    session['mixed_set_initial'] => {en, zh, wrong_count}
    """
    initial = session.get('mixed_set_initial', [])
    errors = [i for i in initial if i['wrong_count'] > 0]
    return render_template('mixed_training_result.html', errors=errors)


if __name__ == '__main__':
    # 若您生产环境是80端口，请改host='0.0.0.0', port=80
    app.run(host='0.0.0.0', port=5000)
