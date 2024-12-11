#app.py

from flask import Flask, render_template, request, jsonify, send_from_directory, session, Response
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
app.config['SESSION_TYPE'] = 'filesystem'  # 使用文件系统存储会话数据
app.config['SESSION_FILE_DIR'] = os.path.join(tempfile.gettempdir(), 'flask_sessions')  # 会话文件存储目录
app.config['SESSION_PERMANENT'] = False
app.config['SECRET_KEY'] = 'safe_safe_safe'  # 替换为您的密钥

# 初始化 Session
Session(app)

# 文本文件路径
TEXT_FILE_PATH = 'store.txt'

# 读取文本文件
def read_text_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    # **修改**：跳过空行
    return [line.strip() for line in lines if line.strip()]

lines = read_text_file(TEXT_FILE_PATH)
total_lines = len(lines)

# 存储临时文件列表
temp_files = []

# 临时音频文件存储根目录
AUDIO_ROOT_DIR = os.path.join(tempfile.gettempdir(), 'flask_audio')
os.makedirs(AUDIO_ROOT_DIR, exist_ok=True)

# 持久化音频文件存储目录
AUDIO_PERSISTENT_DIR = 'audio_files'
os.makedirs(AUDIO_PERSISTENT_DIR, exist_ok=True)

# 翻译存储文件路径
TRANSLATIONS_FILE_PATH = 'translations.json'
translations_lock = threading.Lock()

# 加载已存在的翻译
def load_translations():
    if os.path.exists(TRANSLATIONS_FILE_PATH):
        with open(TRANSLATIONS_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {}

translations = load_translations()

# 注册文件删除函数
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
    """生成一个以 start_index 开始的随机顺序列表。"""
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
        session['play_interval'] = 1  # 秒
    if 'play_mode' not in session:
        session['play_mode'] = 'sequential'  # 'sequential' 或 'random'
    if 'random_order' not in session:
        session['random_order'] = list(range(total_lines))
        random.shuffle(session['random_order'])
    if 'random_index' not in session:
        session['random_index'] = 0

@app.route('/language')
def index():
    return render_template('index.html')

def get_audio_file_path(text):
    text_clean = re.sub(r'<\w+:\s*[^>]+>', '', text)  # 移除所有颜色标签
    text_hash = hashlib.sha256(text_clean.encode('utf-8')).hexdigest()
    filename = f"audio_{text_hash}.mp3"
    file_path = os.path.join(AUDIO_PERSISTENT_DIR, filename)
    return filename, file_path

@app.route('/play', methods=['POST'])
def play():
    global lines, total_lines

    # 重新读取文本文件，防止修改后内容不同步
    lines = read_text_file(TEXT_FILE_PATH)
    total_lines = len(lines)

    if session['play_mode'] == 'sequential':
        if session['current_index'] >= total_lines:
            # 重置到第一行
            session['current_index'] = 0

        line_index = session['current_index']
        text = lines[line_index]
        filename, file_path = get_audio_file_path(text)

        # 如果音频文件已经存在，则不再生成
        if not os.path.exists(file_path):
            # 移除颜色标签后生成音频
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
            # 重新生成随机顺序
            if session['random_order']:
                session['random_order'] = shuffle_random_order(session['random_order'][0])
            else:
                session['random_order'] = shuffle_random_order(0)
            session['random_index'] = 0

        line_index = session['random_order'][session['random_index']]
        text = lines[line_index]
        filename, file_path = get_audio_file_path(text)

        # 如果音频文件已经存在，则不再生成
        if not os.path.exists(file_path):
            # 移除颜色标签后生成音频
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

        # 递增 random_index 以播放下一个随机句子
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
        })  # 返回单行文本和句子索引
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
        # 生成新的随机顺序，以当前行开始
        session['random_order'] = shuffle_random_order(session['current_index'])
        session['random_index'] = 0
    else:
        session['play_mode'] = 'sequential'
        # 保持 current_index 不变，以继续顺序播放
        pass

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
            # 重置到第一行
            session['current_index'] = 0
        return jsonify({'status': 'success', 'current_index': session['current_index']})
    elif session['play_mode'] == 'random':
        if session['random_index'] < total_lines - 1:
            session['random_index'] += 1
            return jsonify({'status': 'success', 'current_index': session['random_order'][session['random_index']]})
        else:
            # 重新洗牌
            session['random_order'] = shuffle_random_order(session['random_order'][0])
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

# 新的扫描资源路由(使用SSE)
@app.route('/scan_resources', methods=['GET'])
def scan_resources():
    def generate_events():
        try:
            # 重新读取文本文件
            current_lines = read_text_file(TEXT_FILE_PATH)
            total = len(current_lines)
            if total == 0:
                yield f"data: {{\"status\":\"done\",\"message\":\"no data\"}}\n\n"
                return

            with translations_lock:
                # 加载最新翻译
                translations = load_translations()

            for i, text in enumerate(current_lines):
                # 生成音频
                filename, file_path = get_audio_file_path(text)
                if not os.path.exists(file_path):
                    text_clean = re.sub(r'<\w+:\s*([^>]+)>', r'\1', text)
                    tts = gTTS(text=text_clean, lang='en', tld='com')
                    tts.save(file_path)

                # 翻译(如果没有则生成并存储)
                with translations_lock:
                    translations = load_translations()
                    if text not in translations:
                        text_clean = re.sub(r'<\w+:\s*([^>]+)>', r'\1', text)
                        translated_text = GoogleTranslator(source='en', target='zh-CN').translate(text_clean)
                        translations[text] = translated_text
                        with open(TRANSLATIONS_FILE_PATH, 'w', encoding='utf-8') as f:
                            json.dump(translations, f, ensure_ascii=False, indent=4)

                progress = (i + 1) / total * 100
                yield f"data: {{\"status\":\"working\",\"progress\":{progress},\"current_index\":{i+1},\"total\":{total}}}\n\n"

            # 全部完成
            yield f"data: {{\"status\":\"done\"}}\n\n"

        except Exception as e:
            yield f"data: {{\"status\":\"error\",\"message\":\"{str(e)}\"}}\n\n"

    return Response(generate_events(), mimetype='text/event-stream')

# 修改后的保存颜色标注的路由
@app.route('/update_word_color', methods=['POST'])
def update_word_color():
    global lines, total_lines  # 将 global 声明移动到函数开头
    try:
        data = request.get_json()
        sentence_index = int(data.get('sentence_index'))
        color_changes = data.get('color_changes', [])  # Expecting a list of {word_index, color}

        if not isinstance(color_changes, list):
            # Single color change
            color_changes = [{
                'word_index': int(data.get('word_index')),
                'color': data.get('color')
            }]

        # 读取当前文本
        if not os.path.exists(TEXT_FILE_PATH):
            return jsonify({'status': 'error', 'message': 'Text file does not exist.'}), 400

        with open(TEXT_FILE_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if sentence_index >= len(lines):
            return jsonify({'status': 'error', 'message': 'Sentence index out of range.'}), 400

        line = lines[sentence_index].strip()

        # Parse the line into words, and mark red words
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
                    word_red.extend([False]*len(plain_words))
            red_text = match.group(1).strip()
            if red_text:
                red_words = red_text.split()
                words.extend(red_words)
                word_red.extend([True]*len(red_words))
            last = end
        if last < len(line):
            plain_text = line[last:].strip()
            if plain_text:
                plain_words = plain_text.split()
                words.extend(plain_words)
                word_red.extend([False]*len(plain_words))

        # Apply color changes
        for change in color_changes:
            word_index = int(change.get('word_index'))
            color = change.get('color')  # 'red' or None

            if word_index < 0 or word_index >= len(words):
                return jsonify({'status': 'error', 'message': f'Word index {word_index} out of range.'}), 400

            if color is not None:
                if not isinstance(color, str) or color.lower() != 'red':
                    return jsonify({'status': 'error', 'message': 'Only red color is supported.'}), 400
                word_red[word_index] = True
            else:
                word_red[word_index] = False

        # Reconstruct the line by wrapping each red word in <red: word> tags
        modified_line = ''
        for i, word in enumerate(words):
            if word_red[i]:
                modified_line += f'<red: {word}> '
            else:
                modified_line += f'{word} '

        modified_line = modified_line.strip()

        # Update the lines list
        lines[sentence_index] = modified_line + '\n'

        # 写回文件
        with open(TEXT_FILE_PATH, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        # 更新全局的 lines 和 total_lines 变量
        lines = read_text_file(TEXT_FILE_PATH)
        total_lines = len(lines)

        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error updating word color: {e}")
        return jsonify({'status': 'error', 'message': 'Could not update word color.'}), 500

# 修改的翻译路由: 优先从translations.json中获取翻译
# 若无翻译则返回 "status":"missing_translation"
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
        return jsonify({'status': 'missing_translation', 'translated_text': ''})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
