# hd.py
# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import signal
import time
import json

app = Flask(__name__)
CORS(app)

# 设置文件路径
base_dir = '/var/lib/myapp/'

recording_status_file = os.path.join(base_dir, 'recording_status.json')
pid_file = os.path.join(base_dir, 'video_stream_pid.txt')
config_file = os.path.join(base_dir, 'config.json')

@app.route('/start-stream', methods=['POST'])
def start_stream():
    data = request.json
    required_fields = ['username', 'password', 'ip', 'camera_group', 'record_duration', 'record_size', 'frame_threshold', 'output_dir']

    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"缺少{field}字段或值无效"}), 400

    try:
        with open(config_file, 'w') as f:
            json.dump(data, f)
        return jsonify({"message": "配置已写入"}), 200
    except Exception as e:
        return jsonify({"error": f"写入配置文件失败: {e}"}), 500

@app.route('/record/start', methods=['POST'])
def start_recording():
    try:
        with open(recording_status_file, 'w') as f:
            json.dump({"recording": True}, f)
        
        process = subprocess.Popen(['/usr/local/bin/1'])  # 路径
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
