import ffmpeg  # 使用 ffmpeg-python 库
import threading
import time
import os
import uuid  # 用于获取MAC地址
import logging
from datetime import datetime  # 用于获取当前时间

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 定义RTSP URL
rtsp_url_1 = "rtsp://admin:tfe123456@10.168.1.66/media/video1"
rtsp_url_2 = "rtsp://admin:tfe123456@10.168.1.67/media/video1"

# 获取设备的MAC地址并格式化
mac_address = uuid.UUID(int=uuid.getnode()).hex[-12:]
mac_folder = f"/home/monster/Desktop/share/DCIM/sp/{mac_address}"

# 用于信号终止的事件
terminate_event = threading.Event()

def record_stream(rtsp_url, output_path):
    try:
        process = (
            ffmpeg
            .input(rtsp_url)
            .output(output_path, vcodec='copy', acodec='aac', audio_bitrate='128k', format='mp4')
            .global_args('-y')
            .run_async(pipe_stdin=True, pipe_stderr=True)
        )

        logging.info(f"正在录制视频和音频到 {output_path} ...")

        while not terminate_event.is_set():
            time.sleep(1)

        logging.info("停止录制...")
        process.stdin.write(b'q')  # 发送停止命令
        process.stdin.close()  # 关闭标准输入
        process.wait()  # 等待 FFmpeg 完全结束

    except Exception as e:
        logging.error(f"录制过程中出错: {e}")
        if process:
            stderr = process.stderr.read().decode()
            logging.debug(f"FFmpeg 错误信息: {stderr}")

def record_video(rtsp_url, output_path):
    try:
        process = (
            ffmpeg
            .input(rtsp_url)
            .output(output_path, vcodec='copy', an=None, format='mp4')
            .global_args('-y')
            .run_async(pipe_stdin=True, pipe_stderr=True)
        )

        logging.info(f"正在录制视频到 {output_path} ...")

        while not terminate_event.is_set():
            time.sleep(1)

        logging.info("停止录制...")
        process.stdin.write(b'q')  # 发送停止命令
        process.stdin.close()  # 关闭标准输入
        process.wait()  # 等待 FFmpeg 完全结束

    except Exception as e:
        logging.error(f"录制过程中出错: {e}")
        if process:
            stderr = process.stderr.read().decode()
            logging.debug(f"FFmpeg 错误信息: {stderr}")

if __name__ == '__main__':
    # 创建基于MAC地址的目录结构
    os.makedirs(mac_folder, exist_ok=True)
    rtspurl1_path = os.path.join(mac_folder, "rtspurl1")
    rtspurl2_path = os.path.join(mac_folder, "rtspurl2")
    os.makedirs(rtspurl1_path, exist_ok=True)
    os.makedirs(rtspurl2_path, exist_ok=True)

    # 获取当前时间并格式化为字符串
    current_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # 定义输出路径，包含时间戳
    output_path_1 = os.path.join(rtspurl1_path, f"{current_time_str}_camera1.mp4")
    output_path_2 = os.path.join(rtspurl2_path, f"{current_time_str}_camera2.mp4")

    # 启动录制线程
    recording_thread_1 = threading.Thread(target=record_stream, args=(rtsp_url_1, output_path_1))
    recording_thread_2 = threading.Thread(target=record_video, args=(rtsp_url_2, output_path_2))

    recording_thread_1.start()
    recording_thread_2.start()

    try:
        while True:
            user_input = input("按 'q' 键停止录制：")
            if user_input.lower() == 'q':
                logging.info("收到关闭信号，正在终止录制...")
                terminate_event.set()
                break
            time.sleep(1)
    except Exception as e:
        logging.error(f"发生错误: {e}")

    # 等待线程结束
    recording_thread_1.join()
    recording_thread_2.join()
    logging.info("录制已终止，文件保存在以下路径：")
    logging.info(output_path_1)
    logging.info(output_path_2)
