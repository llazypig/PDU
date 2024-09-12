# 1.py
# -*- coding: utf-8 -*-
import cv2
import os
import time
import uuid
import sys
from datetime import datetime
import json
import logging

# 设置文件路径
base_dir = '/var/lib/myapp/'

logging.basicConfig(filename=os.path.join(base_dir, 'video_stream.log'),
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s:%(message)s',
                    encoding='utf-8')

recording_status_file = os.path.join(base_dir, 'recording_status.json')
config_file = os.path.join(base_dir, 'config.json')

def is_recording():
    try:
        with open(recording_status_file, 'r') as f:
            status = json.load(f)
        return status.get("recording", False)
    except Exception as e:
        logging.error(f"无法读取录制状态: {e}")
        return False

def get_mac_address():
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> (8 * i)) & 0xff) for i in range(6)])
    return mac.replace(':', '')

def format_ip_address(ip):
    return ip.replace('.', '')

def set_output_dir_and_url(username, password, ip_address, camera_group, output_dir):
    mac_address = get_mac_address()
    formatted_ip = format_ip_address(ip_address)
    merged_output_dir = os.path.join(output_dir, f'{mac_address}/group{camera_group}/')
    rtmp_url = f'rtsp://{username}:{password}@{ip_address}/media/video1'
    if not os.path.exists(merged_output_dir):
        os.makedirs(merged_output_dir)
    logging.info(f"输出目录设置为: {merged_output_dir}")
    return merged_output_dir, rtmp_url, mac_address

def init_video_stream(rtmp_url):
    cap = cv2.VideoCapture(rtmp_url)
    if not cap.isOpened():
        logging.error(f"无法打开视频流: {rtmp_url}")
        sys.exit(1)
    frame_width = int(cap.get(3))
    frame_height = int(cap.get(4))
    return cap, frame_width, frame_height

def process_video(cap, frame_width, frame_height, merged_output_dir, rtmp_url, mac_address, ip_address, record_duration, record_size, frame_threshold):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = None
    ret, prev_frame = cap.read()

    if not ret:
        logging.error("无法读取视频流的第一帧")
        cap.release()
        sys.exit(1)

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    recording = False
    video_path = None
    no_change_start = None
    video_start_time = None
    start_time = None  # 添加开始录制时间

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            logging.error("无法读取视频流帧。")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(prev_gray, gray)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        change = cv2.countNonZero(thresh)

        prev_gray = gray

        if change > frame_threshold:
            if not recording:
                # 如果没有正在录制，则开始录制
                current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                video_path = os.path.join(merged_output_dir, f"{current_time_filename}.mp4")
                out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))
                recording = True
                video_start_time = time.time()
                start_time = video_start_time
                logging.info(f"开始录制视频：{video_path}")
            out.write(frame)
            no_change_start = None  # 重置无变化时间
        else:
            if recording and no_change_start is None:
                # 如果画面没有变化，记录无变化开始时间
                no_change_start = time.time()

        if recording and no_change_start:
            if (time.time() - no_change_start) >= 10:
                # 如果无变化超过10秒，停止录制
                logging.info(f"画面无变化超过10秒，停止写入文件: {video_path}")
                out.release()
                if video_path and os.path.getsize(video_path) < record_size * 1024 * 1024:
                    os.remove(video_path)
                    logging.info(f"文件 {video_path} 被删除，因为它小于{record_size}MB")
                out = None
                recording = False
                no_change_start = None
                video_start_time = None

        if recording and (time.time() - video_start_time) >= record_duration:
            # 如果录制时间达到用户设置的切片时间，保存文件并继续录制
            out.release()
            logging.info(f"录制时间超过用户设置的切片时间，保存文件: {video_path}")
            if video_path and os.path.getsize(video_path) < record_size * 1024 * 1024:
                os.remove(video_path)
                logging.info(f"文件 {video_path} 被删除，因为它小于{record_size}MB")
            current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            video_path = os.path.join(merged_output_dir, f"{current_time_filename}.mp4")
            out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))
            video_start_time = time.time()
            logging.info(f"创建新视频文件：{video_path}")

    cap.release()
    if out:
        out.release()
    logging.info("视频流已关闭")
    sys.exit(0)

if __name__ == "__main__":
    try:
        if not os.path.exists(config_file):
            logging.error("配置文件不存在，等待前端数据...")
            sys.exit(1)
        with open(config_file, 'r') as file:
            config = json.load(file)
            username = config['username']
            password = config['password']
            ip_address = config['ip']
            camera_group = config['camera_group']
            record_duration = int(config['record_duration'])
            record_size = int(config['record_size'])
            frame_threshold = int(config['frame_threshold'])
            output_dir = config['output_dir']

        merged_output_dir, rtmp_url, mac_address = set_output_dir_and_url(username, password, ip_address, camera_group, output_dir)
        cap, frame_width, frame_height = init_video_stream(rtmp_url)
        process_video(cap, frame_width, frame_height, merged_output_dir, rtmp_url, mac_address, ip_address, record_duration, record_size, frame_threshold)
    except Exception as e:
        logging.error(f"发生错误: {e}")
        sys.exit(1)
