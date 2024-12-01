import time
from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_session import Session
from gtts import gTTS
import tempfile
import atexit
from edit_file import edit_file_blueprint  # 确保 edit_file.py 文件存在并定义了 edit_file_blueprint

import subprocess
import sys
import os
import random
import hashlib



app = Flask(__name__)
app.register_blueprint(edit_file_blueprint, url_prefix='/file')

# 配置 Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'  # 使用文件系统存储会话数据
app.config['SESSION_FILE_DIR'] = os.path.join(tempfile.gettempdir(), 'flask_sessions')  # 会话文件存储目录
app.config['SESSION_PERMANENT'] = False
app.config['SECRET_KEY'] = 'your_secret_key_here'  # 替换为您的密钥

# 初始化 Session
Session(app)

# 文本文件路径
TEXT_FILE_PATH = 'store.txt'

# 读取文本文件
def read_text_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
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
    text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
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
            return jsonify({'status': 'no_more_text'})

        line_index = session['current_index']
        text = lines[line_index]
        filename, file_path = get_audio_file_path(text)

        # 如果音频文件已经存在，则不再生成
        if not os.path.exists(file_path):
            tts = gTTS(text=text, lang='en', tld='com')
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
            tts = gTTS(text=text, lang='en', tld='com')
            tts.save(file_path)
            temp_files.append(filename)

        response = {
            'status': 'success',
            'audio_url': f'/audio/{filename}',
            'text': text,
            'current_index': line_index
        }

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
    if 0 <= session['current_index'] < total_lines:
        return jsonify({'text': lines[session['current_index']]})
    else:
        return jsonify({'text': 'no more.'})

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
            return jsonify({'status': 'success', 'current_index': session['current_index']})
        else:
            return jsonify({'status': 'no_more_text'})
    elif session['play_mode'] == 'random':
        if session['random_index'] < total_lines - 1:
            session['random_index'] += 1
            return jsonify({'status': 'success', 'current_index': session['random_order'][session['random_index']]})
        else:
            # Reshuffle if at the end
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
