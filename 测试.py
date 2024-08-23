import av
import cv2
import numpy as np
import wave
import subprocess
import os
import time
import gpiod
from datetime import datetime
from ffpyplayer.player import MediaPlayer

# RTMP流的URL
rtmp_url = 'rtsp://admin:tfe123456@10.168.1.66/media/video1/multicast'
# 保存录制文件的路径
recording_output_dir = '/home/monster/Desktop/share/DCIM/yp/'
# 保存合成文件的路径
merged_output_dir = '/home/monster/Desktop/share/DCIM/hc/'

# GPIO配置
chip_name = "gpiochip6"
line_offset = 0  # GPIO6_A0 (IO1)
debounce_time = 0.05  # 去抖动时间（秒）
lockout_time = 1  # 状态锁定时间（秒）

# 确保输出目录存在
os.makedirs(recording_output_dir, exist_ok=True)
os.makedirs(merged_output_dir, exist_ok=True)

def open_container_and_streams(rtmp_url):
    container = av.open(rtmp_url)
    video_stream = next((s for s in container.streams if s.type == 'video'), None)
    audio_stream = next((s for s in container.streams if s.type == 'audio'), None)

    if video_stream is None or audio_stream is None:
        raise ValueError("No video or audio stream found in the container.")

    return container, video_stream, audio_stream

def initialize_audio_player(audio_stream):
    return MediaPlayer(rtmp_url, ff_opts={'vn': True})  # `vn`: video disabled, only audio

def start_recording_video_and_audio():
    # 初始化GPIO
    chip = gpiod.Chip(chip_name)
    line = chip.get_line(line_offset)
    
    # 请求GPIO线的输入模式
    line.request(consumer="record_toggle", type=gpiod.LINE_REQ_DIR_IN)
    
    last_state = True  # 初始化为高电平（1）
    last_change_time = time.time() - lockout_time
    recording = False
    video_writer = None
    container = None
    video_output_file = os.path.join(recording_output_dir, 'output_video.mp4')
    audio_output_file = os.path.join(recording_output_dir, 'output_audio.wav')
    fourcc = cv2.VideoWriter_fourcc(*'avc1')  # 使用兼容性更好的编解码器标签
    frame_rate = 25

    try:
        container, video_stream, audio_stream = open_container_and_streams(rtmp_url)
        audio_player = initialize_audio_player(audio_stream)
        wave_file = None  # 在启动录制时初始化音频文件

        for packet in container.demux(video_stream, audio_stream):
            try:
                # GPIO 低电平（0）检测
                current_state = line.get_value()
                if current_state == 0 and last_state == 1:
                    current_time = time.time()
                    if current_time - last_change_time > debounce_time:
                        recording = not recording
                        last_change_time = current_time

                        if recording:
                            print("录制已开始")
                            # 初始化音频文件
                            wave_file = wave.open(audio_output_file, 'wb')
                            wave_file.setnchannels(1)
                            wave_file.setsampwidth(2)  # 16-bit samples
                            wave_file.setframerate(16000)  # 使用原始采样率16kHz
                        else:
                            if video_writer is not None:
                                video_writer.release()
                                video_writer = None
                            if wave_file is not None:
                                wave_file.close()  # 停止音频录制
                                wave_file = None
                                print(f"录制已停止，视频已保存到 {video_output_file}")
                                print(f"音频已保存到 {audio_output_file}")

                                # 合成音视频并保存到指定目录
                                merge_audio_video(video_output_file, audio_output_file, merged_output_dir)

                                # 清除旧的容器和流，确保不使用上一次的缓冲区
                                if container is not None:
                                    container.close()
                                container, video_stream, audio_stream = open_container_and_streams(rtmp_url)
                                audio_player = initialize_audio_player(audio_stream)

                last_state = current_state

                if recording and packet.stream.type == 'video':
                    for frame in packet.decode():
                        img = frame.to_ndarray(format='bgr24')

                        if video_writer is None:
                            video_writer = cv2.VideoWriter(video_output_file, fourcc, frame_rate, (img.shape[1], img.shape[0]))
                        video_writer.write(img)

                elif recording and packet.stream.type == 'audio':
                    for frame in packet.decode():
                        audio_data = frame.to_ndarray().astype(np.int16)
                        audio_player.get_frame()  # 同步播放音频
                        if wave_file is not None:
                            wave_file.writeframes(audio_data.tobytes())

                # 按'q'键退出程序
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("程序已退出")
                    break

            except av.AVError as e:
                print(f"Error decoding packet: {e}")

    finally:
        if video_writer is not None:
            video_writer.release()
        if container is not None:
            container.close()

def merge_audio_video(video_file, audio_file, output_dir):
    # 获取当前时间，并格式化为文件名
    current_time_str = datetime.now().strftime("%Y-%m-%d %H\\:%M\\:%S")
    current_time_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = os.path.join(output_dir, f"{current_time_filename}.mp4")
    
    command = [
        'ffmpeg',
        '-y',  # 覆盖现有文件
        '-i', video_file,
        '-i', audio_file,
        '-vf', f"drawtext=text='{current_time_str}':fontcolor=white:fontsize=24:x=(w-text_w-10):y=(h-text_h-10)",
        '-c:v', 'libx264',  # 使用libx264编码器进行压缩
        '-c:a', 'aac',
        '-strict', 'experimental',
        output_file
    ]

    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"最终视频已保存到 {output_file}")
        print(f"ffmpeg output: {result.stdout.decode()}")

    except subprocess.CalledProcessError as e:
        print(f"Error during ffmpeg execution: {e.stderr.decode()}")

if __name__ == "__main__":
    start_recording_video_and_audio()
