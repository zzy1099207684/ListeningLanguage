import time
from flask import Flask, render_template, request, jsonify
from gtts import gTTS
import threading
import pygame
import tempfile
import atexit
from edit_file import edit_file_blueprint  # 确保 edit_file.py 文件存在并定义了 edit_file_blueprint

import subprocess
import sys

# 所需依赖包列表
required_packages = [
    "flask",
    "gtts",
    "pygame",
    "flask-cors"
]

def check_and_install_packages():
    """检查并安装所需的依赖包。"""
    for package in required_packages:
        try:
            # 尝试导入包，检查是否已安装
            __import__(package)
        except ImportError:
            print(f"Package '{package}' is not installed. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        else:
            print(f"Package '{package}' is already installed.")

# 调用依赖检查函数
check_and_install_packages()


app = Flask(__name__)
app.register_blueprint(edit_file_blueprint, url_prefix='/file')

# 文本文件路径
TEXT_FILE_PATH = 'store.txt'

# 初始化 pygame
pygame.mixer.init()

# 读取文本文件
def read_text_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    return [line.strip() for line in lines if line.strip()]

lines = read_text_file(TEXT_FILE_PATH)
current_index = 0
is_playing = False
play_count = 1  # 默认每句只读一次
play_interval = 1  # 间隔时间（秒），默认1秒

# 存储临时文件列表
temp_files = []

# 注册文件删除函数
def delete_temp_files():
    for file in temp_files:
        subprocess.run(['del', file], shell=True)

atexit.register(delete_temp_files)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/play', methods=['POST'])
def play():
    global is_playing
    if not is_playing:
        is_playing = True
        threading.Thread(target=play_audio).start()
    return jsonify({'status': 'playing'})

def play_audio():
    global is_playing, current_index, lines, play_interval
    while is_playing and current_index < len(lines):
        text = lines[current_index]
        for _ in range(play_count):
            if not is_playing:
                return  # 如果播放被停止或暂停，退出
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                output_file = temp_file.name
                tts = gTTS(text=text, lang='en', tld='com')
                tts.save(output_file)
                temp_files.append(output_file)

            pygame.mixer.music.load(output_file)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy() and is_playing:
                time.sleep(0.1)

            temp_files.remove(output_file)
            subprocess.run(['del', output_file], shell=True)

        if is_playing:  # 仅在继续播放时移动到下一句
            current_index += 1
            if current_index < len(lines):  # 在下一句前等待间隔时间
                time.sleep(play_interval)

@app.route('/pause', methods=['POST'])
def pause():
    global is_playing
    if is_playing:
        is_playing = False
        pygame.mixer.music.pause()
    return jsonify({'status': 'paused'})

@app.route('/set_play_options', methods=['POST'])
def set_play_options():
    global play_count, play_interval
    play_count = int(request.form['play_count'])
    play_interval = int(request.form['play_interval'])
    return jsonify({'status': 'options_set'})

@app.route('/get_current_text', methods=['GET'])
def get_current_text():
    if 0 <= current_index < len(lines):
        return jsonify({'text': lines[current_index]})
    else:
        return jsonify({'text': '没有更多文本了。'})

@app.route('/stop', methods=['POST'])
def stop():
    global is_playing
    is_playing = False
    pygame.mixer.music.stop()
    return jsonify({'status': 'stopped'})

if __name__ == '__main__':
    app.run(debug=True)
