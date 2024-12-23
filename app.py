# app.py

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
from dao.store_dao import select_all_store
from dao.translations_dao import select_all_translations, delete_translation, upsert_translation
from dao.setting_dao import get_setting, set_setting
from dao.store_dao import ensure_all_sequences

from edit_file import edit_file_blueprint
from services.app_service import (
    get_audio_file_path,
    read_text_file_by_group,
    shuffle_random_order
)

app = Flask(__name__)
with app.app_context():
    ensure_all_sequences()  # 同步所有表的序列

app.register_blueprint(edit_file_blueprint, url_prefix='/file')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(tempfile.gettempdir(), 'flask_sessions')
app.config['SESSION_PERMANENT'] = False
app.config['SECRET_KEY'] = 'safe_safe_safe'

Session(app)

AUDIO_PERSISTENT_DIR = 'audio_files'
os.makedirs(AUDIO_PERSISTENT_DIR, exist_ok=True)

translations_lock = threading.Lock()


def delete_temp_files():
    pass

atexit.register(delete_temp_files)

@app.before_request
def initialize_session_vars():
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


@app.route('/restart', methods=['GET'])
def restart():
    os.system("sudo systemctl restart your_project_service")
    return "Project restarted successfully!", 200


@app.route('/language')
def index():
    return render_template('index.html')


#########################
# 读取数据库中所有存在的 group
#########################
@app.route('/get_groups', methods=['GET'])
def get_groups():
    rows = select_all_store()
    group_map = {}
    for (sid, gname, line_text) in rows:
        g = gname if gname else ""
        if g not in group_map:
            group_map[g] = []
        group_map[g].append(line_text)
    group_names = list(group_map.keys())
    return jsonify({'groups': group_names})


#########################
# 新增: 读写 setting 表
#########################
@app.route('/get_setting_groups', methods=['GET'])
def get_setting_groups():
    """
    传入 name=? (index_top / edit_choose / combined_training)
    返回 setting 中存的 selected_groups 列表
    """
    name = request.args.get('name', '')
    if not name:
        return jsonify({'status': 'error', 'message': 'missing name'})
    selected = get_setting(name)  # list[str]
    return jsonify({'status': 'success', 'groups': selected})


@app.route('/set_setting_groups', methods=['POST'])
def set_setting_groups():
    """
    用于更新 setting 表中 name=? 对应的 groups(list[str])
    前端可用 JSON 发送 { name: 'xxx', groups: [...] }
    """
    data = request.get_json()
    name = data.get('name', '').strip()
    groups = data.get('groups', [])
    if not name:
        return jsonify({'status': 'error', 'message': 'invalid name'})
    # 强转成字符串列表
    if not isinstance(groups, list):
        return jsonify({'status': 'error', 'message': 'invalid groups'})
    set_setting(name, groups)
    return jsonify({'status': 'success'})


#########################
# 播放逻辑: 读 selected_groups
#########################
def read_text_file_by_multiple_groups(groups):
    """
    若 groups 为空, 读全部
    """
    from dao.store_dao import select_all_store
    rows = select_all_store()
    if not groups:
        return [r[2] for r in rows]
    lines = []
    for (sid, gname, line_text) in rows:
        g = gname if gname else ""
        if g in groups:
            lines.append(line_text)
    return lines


@app.route('/play', methods=['POST'])
def play():
    # main page 顶部下拉 => name='index_top'
    selected_groups = get_setting('index_top')
    current_lines = read_text_file_by_multiple_groups(selected_groups)
    total_lines_current = len(current_lines)
    if total_lines_current == 0:
        return jsonify({'status': 'no_more_text'})

    if session['play_mode'] == 'sequential':
        if session['current_index'] >= total_lines_current:
            session['current_index'] = 0
        line_index = session['current_index']
        text = current_lines[line_index]
        filename, file_path = get_audio_file_path(text)
        if not os.path.exists(file_path):
            tts = gTTS(text=text, lang='en', tld='com')
            tts.save(file_path)
        response = {
            'status': 'success',
            'audio_url': f'/audio/{filename}',
            'text': text,
            'current_index': line_index
        }
        return jsonify(response)

    elif session['play_mode'] == 'random':
        if not session['random_order']:
            session['random_order'] = list(range(total_lines_current))
            random.shuffle(session['random_order'])
            session['random_index'] = 0

        if session['random_index'] >= total_lines_current:
            first_idx = session['random_order'][-1]
            session['random_order'] = shuffle_random_order(first_idx, total_lines_current)
            session['random_index'] = 0

        line_index = session['random_order'][session['random_index']]
        text = current_lines[line_index]
        filename, file_path = get_audio_file_path(text)
        if not os.path.exists(file_path):
            tts = gTTS(text=text, lang='en', tld='com')
            tts.save(file_path)
        response = {
            'status': 'success',
            'audio_url': f'/audio/{filename}',
            'text': text,
            'current_index': line_index
        }
        session['random_index'] += 1
        return jsonify(response)


@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_PERSISTENT_DIR, filename, as_attachment=False)


@app.route('/set_play_options', methods=['POST'])
def set_play_options():
    try:
        session['play_count'] = int(request.form.get('play_count', 1))
        session['play_interval'] = int(request.form.get('play_interval', 1))
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid input.'})
    return jsonify({'status': 'options_set'})


@app.route('/get_play_options', methods=['GET'])
def get_play_options():
    return jsonify({'play_count': session['play_count'], 'play_interval': session['play_interval']})


@app.route('/get_current_text', methods=['GET'])
def get_current_text():
    selected_groups = get_setting('index_top')  # 主页顶部下拉
    current_lines = read_text_file_by_multiple_groups(selected_groups)
    if 0 <= session['current_index'] < len(current_lines):
        return jsonify({
            'status': 'success',
            'text': current_lines[session['current_index']],
            'sentence_index': session['current_index']
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
    current_lines = read_text_file_by_multiple_groups(selected_groups)
    line_count = len(current_lines)

    if session['play_mode'] == 'sequential':
        session['play_mode'] = 'random'
        if line_count > 0:
            current_idx = session.get('current_index', 0)
            if current_idx >= line_count:
                current_idx = 0
            session['random_order'] = shuffle_random_order(current_idx, line_count)
        session['random_index'] = 0
    else:
        session['play_mode'] = 'sequential'
    return jsonify({'status': 'mode_toggled', 'play_mode': session['play_mode']})


@app.route('/get_play_mode', methods=['GET'])
def get_play_mode():
    return jsonify({'play_mode': session['play_mode']})


@app.route('/next', methods=['POST'])
def next_line():
    selected_groups = get_setting('index_top')
    current_lines = read_text_file_by_multiple_groups(selected_groups)
    line_count = len(current_lines)

    if session['play_mode'] == 'sequential':
        if session['current_index'] < line_count - 1:
            session['current_index'] += 1
        else:
            session['current_index'] = 0
        return jsonify({'status': 'success', 'current_index': session['current_index']})

    elif session['play_mode'] == 'random':
        if not session['random_order']:
            session['random_order'] = list(range(line_count))
            random.shuffle(session['random_order'])
            session['random_index'] = 0

        if session['random_index'] < line_count - 1:
            session['random_index'] += 1
        else:
            last_idx = session['random_order'][-1]
            session['random_order'] = shuffle_random_order(last_idx, line_count)
            session['random_index'] = 0
        return jsonify({'status': 'success', 'current_index': session['random_order'][session['random_index']]})
    else:
        return jsonify({'status': 'error', 'message': 'Unknown play mode.'})


@app.route('/previous', methods=['POST'])
def previous_line():
    selected_groups = get_setting('index_top')
    current_lines = read_text_file_by_multiple_groups(selected_groups)
    if session['play_mode'] == 'sequential':
        if session['current_index'] > 0:
            session['current_index'] -= 1
            return jsonify({'status': 'success', 'current_index': session['current_index']})
        else:
            return jsonify({'status': 'no_previous'})
    elif session['play_mode'] == 'random':
        if session['random_index'] > 0:
            session['random_index'] -= 1
            return jsonify({'status': 'success', 'current_index': session['random_order'][session['random_index']]})
        else:
            return jsonify({'status': 'no_previous'})
    else:
        return jsonify({'status': 'error', 'message': 'Unknown play mode.'})


##################################
# 翻译相关
##################################
@app.route('/translate', methods=['POST'])
def translate_text():
    try:
        data = request.get_json()
        text = data.get('text', '')
        text_clean = re.sub(r'<(\w+):\s*([^>]+)>', r'\2', text)
        with translations_lock:
            current_translations = select_all_translations()
        if text_clean in current_translations:
            return jsonify({'status': 'success', 'translated_text': current_translations[text_clean]})
        else:
            return jsonify({'status': 'missing_translation'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/scan_resources', methods=['GET'])
def scan_resources():
    def generate_events():
        try:
            rows = select_all_store()
            all_lines = [r[2] for r in rows]
            if not all_lines:
                yield f"data: {{\"status\":\"done\",\"message\":\"no data\"}}\n\n"
                return

            with translations_lock:
                current_translations = select_all_translations()

            current_texts = set()
            for line in all_lines:
                text_clean = re.sub(r'<\\w+:\\s*([^>]+)>', r'\\1', line)
                current_texts.add(text_clean)

            # 删除旧翻译及音频
            for ttr in list(current_translations.keys()):
                if ttr not in current_texts:
                    delete_translation(ttr)
                    text_hash = hashlib.sha256(ttr.encode('utf-8')).hexdigest()
                    fpath = os.path.join(AUDIO_PERSISTENT_DIR, f'audio_{text_hash}.mp3')
                    if os.path.exists(fpath):
                        os.remove(fpath)

            # 需要生成
            lines_to_scan = []
            for line in all_lines:
                filename, file_path = get_audio_file_path(line)
                text_clean = re.sub(r'<\\w+:\\s*([^>]+)>', r'\\1', line)
                if text_clean not in current_translations or not os.path.exists(file_path):
                    lines_to_scan.append(line)

            if not lines_to_scan:
                yield f"data: {{\"status\":\"done\"}}\n\n"
                return

            for i, text in enumerate(lines_to_scan):
                filename, file_path = get_audio_file_path(text)
                if not os.path.exists(file_path):
                    tts = gTTS(text=text, lang='en', tld='com')
                    tts.save(file_path)

                text_clean = re.sub(r'<\\w+:\\s*([^>]+)>', r'\\1', text)
                if text_clean not in current_translations:
                    translated_text = GoogleTranslator(source='en', target='zh-CN').translate(text_clean)
                    upsert_translation(text_clean, translated_text)
                    current_translations[text_clean] = translated_text

                progress = (i + 1) / len(lines_to_scan) * 100
                yield f"data: {{\"status\":\"working\",\"progress\":{progress},\"current_index\":{i + 1},\"total\":{len(lines_to_scan)}}}\n\n"

            yield f"data: {{\"status\":\"done\"}}\n\n"
        except Exception as e:
            yield f"data: {{\"status\":\"error\",\"message\":\"{str(e)}\"}}\n\n"

    return Response(generate_events(), mimetype='text/event-stream')


##################################
# Mixed training
##################################
@app.route('/mixed_training_setup', methods=['GET'])
def mixed_training_setup():
    """
    这里改为从 setting 表读取 'combined_training' 选组
    若该组为空，则视为全部
    """
    groups = get_setting('combined_training')
    if groups:
        # 只读这些组
        rows = select_all_store()
        lines_in_groups = []
        for (sid, gname, line_text) in rows:
            g = gname if gname else ""
            if g in groups:
                lines_in_groups.append(line_text)
        lines_in_group = list(set(lines_in_groups))
    else:
        # 若没有设置，就读取所有
        rows = select_all_store()
        lines_in_group = [r[2] for r in rows]

    if len(lines_in_group) == 0:
        return redirect(url_for('index'))

    all_translations = select_all_translations()
    import random
    sample_count = min(10, len(lines_in_group))
    chosen_lines = random.sample(lines_in_group, sample_count)

    mixed_set = []
    for l in chosen_lines:
        text_clean = re.sub(r'<\\w+:\\s*([^>]+)>', r'\\1', l)
        zh_trans = all_translations.get(text_clean, None)
        if zh_trans is None:
            zh_trans = "未找到翻译，请先进行资源扫描（scan new resource）以生成翻译。"
        direction = random.choice(['en2zh', 'zh2en'])
        mixed_set.append({
            'en': text_clean,
            'zh': zh_trans,
            'wrong_count': 0,
            'direction': direction
        })

    session['mixed_set_initial'] = [dict(item) for item in mixed_set]
    session['mixed_set'] = mixed_set
    return redirect(url_for('mixed_training'))


@app.route('/mixed_training')
def mixed_training():
    return render_template('mixed_training.html')


@app.route('/mixed_training_next', methods=['GET'])
def mixed_training_next():
    super_mixed = request.args.get('super_mixed', '0')
    mixed_set = session.get('mixed_set', [])
    if not mixed_set:
        return jsonify({'status': 'done'})

    import random
    sentence = random.choice(mixed_set)
    remaining_count = len(mixed_set)

    if super_mixed == '1':
        show_lang = random.choice(['en', 'zh'])
    else:
        if sentence['direction'] == 'en2zh':
            show_lang = 'en'
        else:
            show_lang = 'zh'

    response = {
        'status': 'success',
        'show_text': sentence[show_lang],
        'lang': show_lang,
        'remaining_count': remaining_count
    }

    text_clean = sentence['en']
    filename, file_path = get_audio_file_path(text_clean)
    if not os.path.exists(file_path):
        tts = gTTS(text=text_clean, lang='en', tld='com')
        tts.save(file_path)
    response['audio_url'] = f'/audio/{filename}'

    return jsonify(response)


@app.route('/mixed_training_mark', methods=['POST'])
def mixed_training_mark():
    data = request.get_json()
    show_text = data.get('show_text', '').strip()
    choice = data.get('choice', '')
    lang = data.get('lang', 'en')

    mixed_set = session.get('mixed_set', [])
    found = None
    for item in mixed_set:
        if item[lang] == show_text:
            found = item
            break
    if not found:
        return jsonify({'status': 'error', 'message': 'Sentence not found'})

    other_lang = 'zh' if lang == 'en' else 'en'
    other_text = found[other_lang]

    if choice == 'reveal':
        return jsonify({'status': 'success', 'other_text': other_text})
    elif choice == 'known':
        mixed_set.remove(found)
        session['mixed_set'] = mixed_set
        return jsonify({'status': 'success', 'other_text': other_text, 'done_for_this': True})
    else:
        # unremembered
        found['wrong_count'] += 1
        session['mixed_set'] = mixed_set
        return jsonify({'status': 'success', 'other_text': other_text, 'done_for_this': False})


@app.route('/mixed_training_check_finish', methods=['GET'])
def mixed_training_check_finish():
    mixed_set = session.get('mixed_set', [])
    if len(mixed_set) == 0:
        return jsonify({'status': 'finished'})
    else:
        return jsonify({'status': 'not_finished'})


@app.route('/mixed_training_update_initial', methods=['POST'])
def mixed_training_update_initial():
    data = request.get_json()
    show_text = data.get('show_text', '').strip()
    lang = data.get('lang', 'en')
    choice = data.get('choice', '')

    initial_set = session.get('mixed_set_initial', [])
    for item in initial_set:
        if item[lang] == show_text:
            if choice == 'unknown':
                item['wrong_count'] += 1
    session['mixed_set_initial'] = initial_set
    return jsonify({'status': 'success'})


@app.route('/mixed_training_all_done')
def mixed_training_all_done():
    return redirect(url_for('mixed_training_finish'))


@app.route('/mixed_training_finish')
def mixed_training_finish():
    initial_set = session.get('mixed_set_initial', [])
    errors = [item for item in initial_set if item['wrong_count'] > 0]
    return render_template('mixed_training_result.html', errors=errors)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
