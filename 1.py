import ffmpeg 
import threading
import time
import os
import uuid 
import logging
from datetime import datetime 

# 配置日志记录到文件
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='/media/monster/数据/logfile.log', 
    filemode='w'  
)

# 定义RTSP URL
rtsp_url_1 = "rtsp://admin:tfe123456@10.168.1.66/media/video1"
rtsp_url_2 = "rtsp://admin:tfe123456@10.168.1.67/media/video1"

# 获取设备的MAC地址并格式化
mac_address = uuid.UUID(int=uuid.getnode()).hex[-12:]
mac_folder = f"/media/monster/数据/sp/{mac_address}" 

# 用于信号终止的事件
terminate_event = threading.Event()

def record_stream(rtsp_url, output_path):
    try:
        process = (
            ffmpeg
            .input(rtsp_url, rtsp_flags='prefer_tcp', stimeout='5000000', buffer_size='2000000')  # 设置连接和缓冲区
            .output(output_path, vcodec='copy', acodec='aac', audio_bitrate='128k', format='mp4')
            .global_args('-y', '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '2')  # 强制保持连接
            .run_async(pipe_stdin=True, pipe_stderr=True)
        )

        logging.info(f"正在录制视频和音频到 {output_path} ...")

        while not terminate_event.is_set():
            if process.poll() is not None:
                logging.error(f"FFmpeg意外退出，停止录制: {output_path}")
                stderr = process.stderr.read().decode()
                logging.debug(f"FFmpeg 错误信息: {stderr}")
                return
            time.sleep(1)

        logging.info("停止录制...")
        process.stdin.write(b'q')  
        process.stdin.close() 
        process.wait()  # 等待 FFmpeg 完全结束

    except Exception as e:
        logging.error(f"录制过程中出错: {e}")
        if process:
            stderr = process.stderr.read().decode()
            logging.debug(f"FFmpeg 错误信息: {stderr}")

        # 确保进程被终止
        if process and process.poll() is None:
            process.terminate()
            process.wait()
        logging.info(f"FFmpeg已被终止: {output_path}")

    finally:
        if process:
            process.kill()  # 强制杀死进程
            logging.info(f"FFmpeg进程已被强制终止: {output_path}")

def record_video(rtsp_url, output_path):
    try:
        process = (
            ffmpeg
            .input(rtsp_url, rtsp_flags='prefer_tcp', stimeout='5000000', buffer_size='2000000')  # 连接和缓冲区
            .output(output_path, vcodec='copy', an=None, format='mp4')
            .global_args('-y', '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '2')  # 强制保持连接
            .run_async(pipe_stdin=True, pipe_stderr=True)
        )

        logging.info(f"正在录制视频到 {output_path} ...")

        while not terminate_event.is_set():
            if process.poll() is not None:
                logging.error(f"FFmpeg意外退出，停止录制: {output_path}")
                stderr = process.stderr.read().decode()
                logging.debug(f"FFmpeg 错误信息: {stderr}")
                return
            time.sleep(1)

        logging.info("停止录制...")
        process.stdin.write(b'q') 
        process.stdin.close() 
        process.wait()  # 等待 FFmpeg 完全结束

    except Exception as e:
        logging.error(f"录制过程中出错: {e}")
        if process:
            stderr = process.stderr.read().decode()
            logging.debug(f"FFmpeg 错误信息: {stderr}")

        # 确保进程被终止
        if process and process.poll() is None:
            process.terminate()
            process.wait()
        logging.info(f"FFmpeg进程已被终止: {output_path}")

    finally:
        if process:
            process.kill()  # 强制杀死进程
            logging.info(f"FFmpeg终止: {output_path}")

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
            if os.path.exists("stop_signal.txt"):
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

    # 删除停止信号文件
    if os.path.exists("stop_signal.txt"):
        os.remove("stop_signal.txt")
        logging.info("停止信号文件已删除")
