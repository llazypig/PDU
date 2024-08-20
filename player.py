import gpiod
import av
import cv2
import numpy as np
import wave
import subprocess
import os
import time
import logging
from ffpyplayer.player import MediaPlayer

# 定义GPIO芯片和引脚号
chip_name = "gpiochip6"
line_offset = 0  # GPIO6_A0 (IO1)
debounce_time = 0.05  # 去抖动时间（秒）
lockout_time = 1  # 状态锁定时间（秒）

# RTMP流的URL
rtmp_url = 'rtsp://admin:tfe123456@10.168.1.66/media/video1/multicast'
# 保存文件的路径
output_dir = '/home/monster/Desktop/share/DCIM/'

# 设置日志记录
logging.basicConfig(level=logging.INFO)

# 确保输出目录存在
os.makedirs(output_dir, exist_ok=True)

def open_container_and_streams(rtmp_url):
    container = av.open(rtmp_url)
    video_stream = next((s for s in container.streams if s.type == 'video'), None)
    audio_stream = next((s for s in container.streams if s.type == 'audio'), None)
    if video_stream is None or audio_stream is None:
        raise ValueError("No video or audio stream found in the container.")
    return container, video_stream, audio_stream

def initialize_audio_player(audio_stream):
    return MediaPlayer(rtmp_url, ff_opts={'vn': True})  # `vn`:视频禁用，只有音频

def check_gpio_state(line):
    initial_value = line.get_value()
    time.sleep(debounce_time)  # 去抖动
    final_value = line.get_value()
    if initial_value == final_value:
        return final_value
    else:
        return None  # 状态不稳定，返回None

def start_recording_video_and_audio():
    try:
        # 获取音视频流
        container, video_stream, audio_stream = open_container_and_streams(rtmp_url)

        # 显示窗口
        cv2.namedWindow('Video Frame', cv2.WINDOW_NORMAL)

        # 初始化音频播放器
        audio_player = initialize_audio_player(audio_stream)
        
        # 录制的WAV文件
        audio_output_file = os.path.join(output_dir, 'output_audio.wav')
        wave_file = wave.open(audio_output_file, 'wb')
        wave_file.setnchannels(1)
        wave_file.setsampwidth(2)  # 16-bit samples
        wave_file.setframerate(16000)  # 采样率16kHz

        # 初始化视频录制的相关变量
        recording = False
        video_writer = None
        video_output_file = os.path.join(output_dir, 'output_video.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'H264')
        frame_rate = 25
        last_signal_time = 0  # 记录上次信号时间

        # GPIO 芯片并获取线
        chip = gpiod.Chip(chip_name)
        line = chip.get_line(line_offset)
        line.request(consumer="gpio_reader", type=gpiod.LINE_REQ_DIR_IN)

        # 处理音视频流
        for packet in container.demux(video_stream, audio_stream):
            try:
                if packet.stream.type == 'video':
                    for frame in packet.decode():
                        img = frame.to_ndarray(format='bgr24')
                        cv2.imshow('Video Frame', img)

                        # 检查GPIO状态
                        gpio_value = check_gpio_state(line)
                        current_time = time.time()

                        if gpio_value is not None and gpio_value == 1 and (current_time - last_signal_time > lockout_time):
                            last_signal_time = current_time
                            if not recording:
                                recording = True
                                video_writer = cv2.VideoWriter(video_output_file, fourcc, frame_rate, (img.shape[1], img.shape[0]))
                                start_time = time.time()  # 记录录制开始时间
                                logging.info("录制已开始")
                            else:
                                recording = False
                                if video_writer is not None:
                                    video_writer.release()
                                    video_writer = None
                                    wave_file.close()  # 停止音频录制
                                    logging.info(f"录制已停止，视频已保存到 {video_output_file}")
                                    logging.info(f"音频已保存到 {audio_output_file}")

                                    # 合成音视频
                                    merge_audio_video(video_output_file, audio_output_file, output_dir)
                                    return

                        if recording:
                            video_writer.write(img)

                        key = cv2.waitKey(1) & 0xFF
                        if key == ord('q'):
                            break

                elif packet.stream.type == 'audio':
                    for frame in packet.decode():
                        if recording:
                            audio_data = frame.to_ndarray().astype(np.int16)  # 强制转换为16-bit
                            audio_player.get_frame()  # 同步播放音频
                            wave_file.writeframes(audio_data.tobytes())

            except av.AVError as e:
                logging.error(f"Error decoding packet: {e}")

    finally:
        cv2.destroyAllWindows()
        if 'video_writer' in locals() and video_writer is not None:
            video_writer.release()
        if 'container' in locals():
            container.close()

def merge_audio_video(video_file, audio_file, output_dir):
    output_file = os.path.join(output_dir, 'final_output.mp4')
    command = [
        'ffmpeg',
        '-y',               # 覆盖现有文件
        '-i', video_file,
        '-i', audio_file,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-strict', 'experimental',
        output_file
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info(f"最终视频已保存到 {output_file}")
        logging.info(f"ffmpeg output: {result.stdout.decode()}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during ffmpeg execution: {e.stderr.decode()}")

if __name__ == "__main__":
    start_recording_video_and_audio()
