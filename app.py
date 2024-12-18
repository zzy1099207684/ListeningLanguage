# app.py

from flask import Flask, render_template, request, jsonify, send_from_directory, session, Response, redirect, url_for
from flask_session import Session
from gtts import gTTS
import tempfile
import atexit
from edit_file import edit_file_blueprint

import os
import random
import hashlib
import json
from deep_translator import GoogleTranslator
import threading
import re

app = Flask(__name__)
app.register_blueprint(edit_file_blueprint, url_prefix='/file')

# 配置 Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(tempfile.gettempdir(), 'flask_sessions')
app.config['SESSION_PERMANENT'] = False
app.config['SECRET_KEY'] = 'safe_safe_safe'

Session(app)

TEXT_FILE_PATH = 'store.txt'


def read_text_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    return [line.strip() for line in lines if line.strip()]


lines = read_text_file(TEXT_FILE_PATH)
total_lines = len(lines)

temp_files = []
AUDIO_ROOT_DIR = os.path.join(tempfile.gettempdir(), 'flask_audio')
os.makedirs(AUDIO_ROOT_DIR, exist_ok=True)
AUDIO_PERSISTENT_DIR = 'audio_files'
os.makedirs(AUDIO_PERSISTENT_DIR, exist_ok=True)

TRANSLATIONS_FILE_PATH = 'translations.json'
translations_lock = threading.Lock()


def load_translations():
    if os.path.exists(TRANSLATIONS_FILE_PATH):
        with open(TRANSLATIONS_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {}


translations = load_translations()


def delete_temp_files():
    try:
        for session_dir in os.listdir(AUDIO_ROOT_DIR):
            session_path = os.path.join(AUDIO_ROOT_DIR, session_dir)
            if os.path.isdir(session_path):
                for filename in os.listdir(session_path):
                    file_path = os.path.join(session_path, filename)
                    os.remove(file_path)
                os.rmdir(session_path)
    except Exception as e:
        print(f"Error deleting temp audio files: {e}")


atexit.register(delete_temp_files)


def shuffle_random_order(start_index):
    indices = list(range(total_lines))
    if start_index in indices:
        indices.remove(start_index)
    random.shuffle(indices)
    return [start_index] + indices


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
        session['random_order'] = list(range(total_lines))
        random.shuffle(session['random_order'])
    if 'random_index' not in session:
        session['random_index'] = 0


@app.route('/language')
def index():
    return render_template('index.html')


def get_audio_file_path(text):
    text_clean = re.sub(r'<\w+:\s*[^>]+>', '', text)
    text_hash = hashlib.sha256(text_clean.encode('utf-8')).hexdigest()
    filename = f"audio_{text_hash}.mp3"
    file_path = os.path.join(AUDIO_PERSISTENT_DIR, filename)
    return filename, file_path


@app.route('/play', methods=['POST'])
def play():
    global lines, total_lines
    lines = read_text_file(TEXT_FILE_PATH)
    total_lines = len(lines)

    if session['play_mode'] == 'sequential':
        if session['current_index'] >= total_lines:
            session['current_index'] = 0
        line_index = session['current_index']
        text = lines[line_index]
        filename, file_path = get_audio_file_path(text)
        if not os.path.exists(file_path):
            text_clean = re.sub(r'<\w+:\s*([^>]+)>', r'\1', text)
            tts = gTTS(text=text_clean, lang='en', tld='com')
            tts.save(file_path)
            temp_files.append(filename)
        response = {
            'status': 'success',
            'audio_url': f'/audio/{filename}',
            'text': text,
            'current_index': line_index
        }
        return jsonify(response)

    elif session['play_mode'] == 'random':
        if session['random_index'] >= total_lines:
            if session['random_order']:
                session['random_order'] = shuffle_random_order(session['random_order'][0])
            else:
                session['random_order'] = shuffle_random_order(0)
            session['random_index'] = 0

        line_index = session['random_order'][session['random_index']]
        text = lines[line_index]
        filename, file_path = get_audio_file_path(text)
        if not os.path.exists(file_path):
            text_clean = re.sub(r'<\w+:\s*([^>]+)>', r'\1', text)
            tts = gTTS(text=text_clean, lang='en', tld='com')
            tts.save(file_path)
            temp_files.append(filename)
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
    current_lines = read_text_file(TEXT_FILE_PATH)
    current_total = len(current_lines)
    if 'current_index' not in session:
        session['current_index'] = 0
    if 0 <= session['current_index'] < current_total:
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
    if session['play_mode'] == 'sequential':
        session['play_mode'] = 'random'
        session['random_order'] = shuffle_random_order(session['current_index'])
        session['random_index'] = 0
    else:
        session['play_mode'] = 'sequential'
    return jsonify({'status': 'mode_toggled', 'play_mode': session['play_mode']})


@app.route('/get_play_mode', methods=['GET'])
def get_play_mode():
    return jsonify({'play_mode': session['play_mode']})


@app.route('/next', methods=['POST'])
def next_line():
    if session['play_mode'] == 'sequential':
        if session['current_index'] < total_lines - 1:
            session['current_index'] += 1
        else:
            session['current_index'] = 0
        return jsonify({'status': 'success', 'current_index': session['current_index']})
    elif session['play_mode'] == 'random':
        if session['random_index'] < total_lines - 1:
            session['random_index'] += 1
            return jsonify({'status': 'success', 'current_index': session['random_order'][session['random_index']]})
        else:
            session['random_order'] = shuffle_random_order(session['random_order'][session['random_index']])
            session['random_index'] = 0
            return jsonify({'status': 'success', 'current_index': session['random_order'][session['random_index']]})
    else:
        return jsonify({'status': 'error', 'message': 'Unknown play mode.'})


@app.route('/previous', methods=['POST'])
def previous_line():
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


@app.route('/scan_resources', methods=['GET'])
def scan_resources():
    def generate_events():
        try:
            current_lines = read_text_file(TEXT_FILE_PATH)
            unique_lines = list(set(current_lines))
            processed_lines = [line.replace('.', '') for line in unique_lines]

            if processed_lines:
                processed_lines.sort()
                with open(TEXT_FILE_PATH, 'w', encoding='utf-8') as f:
                    for pl in processed_lines:
                        f.write(pl.strip() + '\n')

            updated_lines = read_text_file(TEXT_FILE_PATH)
            total = len(updated_lines)
            if total == 0:
                yield f"data: {{\"status\":\"done\",\"message\":\"no data\"}}\n\n"
                return

            with translations_lock:
                current_translations = load_translations()

            for i, text in enumerate(updated_lines):
                filename, file_path = get_audio_file_path(text)
                text_clean = re.sub(r'<\w+:\s*([^>]+)>', r'\1', text)

                if not os.path.exists(file_path):
                    tts = gTTS(text=text_clean, lang='en', tld='com')
                    tts.save(file_path)

                if text_clean not in current_translations:
                    translated_text = GoogleTranslator(source='en', target='zh-CN').translate(text_clean)
                    current_translations[text_clean] = translated_text

                progress = (i + 1) / total * 100
                yield f"data: {{\"status\":\"working\",\"progress\":{progress},\"current_index\":{i + 1},\"total\":{total}}}\n\n"

            with translations_lock:
                with open(TRANSLATIONS_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(current_translations, f, ensure_ascii=False, indent=4)

            yield f"data: {{\"status\":\"done\"}}\n\n"

        except Exception as e:
            yield f"data: {{\"status\":\"error\",\"message\":\"{str(e)}\"}}\n\n"

    return Response(generate_events(), mimetype='text/event-stream')


@app.route('/update_word_color', methods=['POST'])
def update_word_color():
    global lines, total_lines
    try:
        data = request.get_json()
        sentence_index = int(data.get('sentence_index'))
        color_changes = data.get('color_changes', [])

        if not isinstance(color_changes, list):
            color_changes = [{
                'word_index': int(data.get('word_index')),
                'color': data.get('color')
            }]

        if not os.path.exists(TEXT_FILE_PATH):
            return jsonify({'status': 'error', 'message': 'Text file does not exist.'}), 400

        with open(TEXT_FILE_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if sentence_index >= len(lines):
            return jsonify({'status': 'error', 'message': 'Sentence index out of range.'}), 400

        line = lines[sentence_index].strip()

        word_red = []
        words = []
        pattern = re.compile(r'<red:\s*([^>]+)>')
        last = 0
        for match in pattern.finditer(line):
            start, end = match.span()
            if start > last:
                plain_text = line[last:start].strip()
                if plain_text:
                    plain_words = plain_text.split()
                    words.extend(plain_words)
                    word_red.extend([False] * len(plain_words))
            red_text = match.group(1).strip()
            if red_text:
                red_words = red_text.split()
                words.extend(red_words)
                word_red.extend([True] * len(red_words))
            last = end
        if last < len(line):
            plain_text = line[last:].strip()
            if plain_text:
                plain_words = plain_text.split()
                words.extend(plain_words)
                word_red.extend([False] * len(plain_words))

        for change in color_changes:
            word_index = int(change.get('word_index'))
            color = change.get('color')
            if word_index < 0 or word_index >= len(words):
                return jsonify({'status': 'error', 'message': f'Word index {word_index} out of range.'}), 400

            if color is not None:
                if not isinstance(color, str) or color.lower() != 'red':
                    return jsonify({'status': 'error', 'message': 'Only red color is supported.'}), 400
                word_red[word_index] = True
            else:
                word_red[word_index] = False

        modified_line = ''
        for i, word in enumerate(words):
            if word_red[i]:
                modified_line += f'<red: {word}> '
            else:
                modified_line += f'{word} '
        modified_line = modified_line.strip()

        lines[sentence_index] = modified_line + '\n'

        with open(TEXT_FILE_PATH, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        lines = read_text_file(TEXT_FILE_PATH)
        total_lines = len(lines)

        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error updating word color: {e}")
        return jsonify({'status': 'error', 'message': 'Could not update word color.'}), 500


@app.route('/translate', methods=['POST'])
def translate_text():
    data = request.get_json()
    text = data.get('text', '')
    text_clean = re.sub(r'<\w+:\s*([^>]+)>', r'\1', text)
    with translations_lock:
        translations = load_translations()
    if text_clean in translations:
        translated_text = translations[text_clean]
        return jsonify({'status': 'success', 'translated_text': translated_text})
    else:
        # 若没找到，说明当前text_clean可能是中文，需要找对应英文
        mixed_set = session.get('mixed_set', [])
        for item in mixed_set:
            if item['zh'] == text_clean:
                # 找到对应的英文
                return jsonify({'status': 'success', 'translated_text': item['en']})
        return jsonify({'status': 'missing_translation', 'translated_text': ''})


@app.route('/translate_word', methods=['POST'])
def translate_word():
    data = request.get_json()
    word = data.get('text', '').strip()
    if not word:
        return jsonify({'status': 'error', 'message': 'No text provided.'}), 400
    try:
        translated_word = GoogleTranslator(source='auto', target='zh-CN').translate(word)
        return jsonify({'status': 'success', 'translated_text': translated_word})
    except Exception as e:
        print(f"Error translating word '{word}': {e}")
        return jsonify({'status': 'error', 'message': 'Translation failed.'}), 500


@app.route('/mixed_training_setup', methods=['GET'])
def mixed_training_setup():
    global lines
    lines = read_text_file(TEXT_FILE_PATH)
    if len(lines) == 0:
        return redirect(url_for('index'))
    sample_count = min(10, len(lines))
    chosen_lines = random.sample(lines, sample_count)

    with translations_lock:
        all_translations = load_translations()

    mixed_set = []
    # 在此处决定每个句子的初始方向: 50%概率en2zh(看英知中), 50%概率zh2en(看中知英)
    for l in chosen_lines:
        text_clean = re.sub(r'<\w+:\s*([^>]+)>', r'\1', l)
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
    super_mixed = request.args.get('super_mixed', '0')  # '1' 表示选中，'0' 表示未选中
    mixed_set = session.get('mixed_set', [])
    if not mixed_set:
        return jsonify({'status': 'done'})

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

    if show_lang == 'en':
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

    if choice == 'known':
        mixed_set.remove(found)
        session['mixed_set'] = mixed_set
        return jsonify({'status': 'success', 'other_text': other_text, 'done_for_this': True})
    else:
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
