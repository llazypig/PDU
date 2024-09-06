# /usr/TFE/my_env/fl/hd.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import signal
import time
import json

app = Flask(__name__)
CORS(app)

recording_status_file = '/usr/TFE/my_env/fl/recording_status.json'
pid_file = '/usr/TFE/my_env/fl/video_stream_pid.txt'

@app.route('/start-stream', methods=['POST'])
def start_stream():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    ip = data.get('ip')

    if not username or not password or not ip:
        return jsonify({"error": "无效的输入数据"}), 400

    try:
        with open('/usr/TFE/my_env/fl/data.txt', 'w') as file:
            file.write(f"{username}\n{password}\n{ip}\n")
        return jsonify({"message": "数据已写入"}), 200
    except Exception as e:
        return jsonify({"error": "写入数据文件失败"}), 500

@app.route('/record/start', methods=['POST'])
def start_recording():
    try:
        with open(recording_status_file, 'w') as f:
            json.dump({"recording": True}, f)
        
        process = subprocess.Popen(['python3', '/usr/TFE/my_env/fl/1.py'])
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        
        return jsonify({"message": "视频流已启动，开始录制"}), 200
    except Exception as e:
        return jsonify({"error": f"启动视频流失败: {e}"}), 500

@app.route('/record/stop', methods=['POST'])
def stop_recording():
    try:
        with open(recording_status_file, 'w') as f:
            json.dump({"recording": False}, f)

        time.sleep(2)  # 等待视频文件保存完成
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)  # 终止进程
            os.remove(pid_file)  # 删除PID文件
        return jsonify({"message": "停止录制并结束进程"}), 200
    except Exception as e:
        return jsonify({"error": f"无法停止录制或结束程序: {e}"}), 500

if __name__ == '__main__':
    if not os.path.exists(recording_status_file):
        with open(recording_status_file, 'w') as f:
            json.dump({"recording": False}, f)
    app.run(host='0.0.0.0', port=5000)
