import cv2
import os
import time
import logging
import sys
from datetime import datetime

def process_video(cap, frame_width, frame_height, merged_output_dir, rtmp_url, mac_address, ip_address, record_duration, record_size, frame_threshold, mqtt_client):
    """
    处理视频流，根据帧变化情况进行录制，并在结束时上报视频信息。

    :param cap: cv2.VideoCapture 对象
    :param frame_width: 视频帧宽度
    :param frame_height: 视频帧高度
    :param merged_output_dir: 视频保存目录
    :param rtmp_url: RTMP 流 URL
    :param mac_address: 设备 MAC 地址
    :param ip_address: 摄像头 IP 地址
    :param record_duration: 录制时长（秒）
    :param record_size: 录制文件的最小大小（MB）
    :param frame_threshold: 帧变化阈值
    :param mqtt_client: MQTT 客户端实例，用于上报视频信息
    """
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = None
    ret, prev_frame = cap.read()

    if not ret:
        logging.error("无法读取视频流的第一帧")
        cap.release()
        sys.exit(1)

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    recording = False
    start_time = None
    video_path = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            logging.error("无法读取视频流帧。")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(prev_gray, gray)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        change = cv2.countNonZero(thresh)

        # 更新前一帧
        prev_gray = gray

        # 检查是否需要开始新的录制
        current_recording = is_recording()  # 假设该函数定义在其他地方
        if current_recording and not recording:
            # 开始录制新文件
            current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            video_path = os.path.join(merged_output_dir, f"{current_time_filename}.mp4")
            out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))
            recording = True
            start_time = int(time.time() * 1000)  # 记录开始时间戳（毫秒）
            logging.info(f"开始录制视频：{video_path}")

        # 如果正在录制且帧变化满足阈值，则写入帧
        if change > frame_threshold and recording:
            out.write(frame)

        # 检查是否需要停止录制
        elif not current_recording and recording:
            # 停止录制
            recording = False
            if out:
                out.release()
                out = None
                end_time = int(time.time() * 1000)  # 记录结束时间戳（毫秒）
                file_size = os.path.getsize(video_path) // 1024  # 文件大小，单位：KB

                # 构建视频信息
                video_info = {
                    "startTime": start_time,
                    "endTime": end_time,
                    "recordDuration": (end_time - start_time) // 1000,  # 录制时长，单位：秒
                    "fileSize": file_size,
                    "fileType": "mp4"
                }
                # 发送视频信息到 MQTT
                mqtt_client.handle_video_info(video_info)
                logging.info(f"文件 {video_path} 已保存完成")

        # 录制超时检查
        if recording and (int(time.time() * 1000) - start_time) >= record_duration * 1000:
            out.release()
            # 检查文件大小
            if video_path and os.path.getsize(video_path) < record_size * 1024 * 1024:  # 最小文件大小检查
                os.remove(video_path)
                logging.info(f"文件 {video_path} 被删除，因为它小于{record_size}MB")
            else:
                logging.info(f"文件 {video_path} 已完成录制，准备新的文件")

            # 创建新的视频文件
            current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            video_path = os.path.join(merged_output_dir, f"{current_time_filename}.mp4")
            out = cv2.VideoWriter(video_path, fourcc, 20.0, (frame_width, frame_height))
            start_time = int(time.time() * 1000)
            logging.info(f"创建新视频文件：{video_path}")

    # 释放资源
    cap.release()
    if out:
        out.release()
    logging.info("视频流已关闭")
    sys.exit(0)
