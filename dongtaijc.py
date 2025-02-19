import cv2
import os
import time
import uuid
import sys
import json
import logging
import threading
import subprocess
import numpy as np
from datetime import datetime
import shutil

# 设置文件路径
base_dir = '/usr/local/bin/'
logging.basicConfig(filename=os.path.join(base_dir, 'video_stream.log'),
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s:%(message)s',
                    encoding='utf-8')

config_file = os.path.join(base_dir, 'config.json')

def get_mac_address():
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> (8 * i)) & 0xff) for i in range(6)])
    return mac.replace(':', '')

def set_output_dir_and_url(username, password, ip_address, camera_group, output_dir):
    mac_address = get_mac_address()
    # 修改合并输出目录路径
    merged_output_dir = os.path.join(output_dir, f'{mac_address}/{camera_group}FireDoor/')
    rtmp_url = f'rtsp://{username}:{password}@{ip_address}/media/video1'
    if not os.path.exists(merged_output_dir):
        os.makedirs(merged_output_dir)
    return merged_output_dir, rtmp_url

# 启动 FFmpeg 录制线程
def start_ffmpeg_recording(rtmp_url, ts_dir):
    # 使用时间格式化字符串生成 .ts 文件名
    segment_filename = os.path.join(ts_dir, "%Y-%m-%d_%H-%M-%S.ts")
    output_path = os.path.join(ts_dir, "output.m3u8")
    
    while True:
        ffmpeg_command = [
            "ffmpeg", "-i", rtmp_url, "-c", "copy", "-f", "hls", 
            "-hls_time", "1", "-hls_list_size", "20", 
            "-hls_segment_filename", segment_filename, "-strftime", "1", output_path
        ]
        
        # 尝试连接 RTMP 流
        result = subprocess.run(ffmpeg_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info("FFmpeg 录制成功")
        else:
            logging.error(f"FFmpeg 录制失败: {result.stderr}")
            logging.info("等待 10 秒后重试连接 RTMP 流")
            time.sleep(10)  # 等待 10 秒后重试

def create_file_list(ts_files, output_list):
    """ 创建一个文件列表，将所有 .ts 文件写入指定的输出列表文件中 """
    with open(output_list, 'w') as f:
        for ts_file in ts_files:
            f.write(f"file '{ts_file}'\n")  # 将每个 .ts 文件路径写入文件

def combine_ts_to_mp4(ts_files, output_dir, record_min_size, camera_id, camera_group):
    """ 合并 .ts 文件为一个 .mp4 文件，并进行必要的检查和处理 """
    if not ts_files:
        logging.error("没有可合成的 .ts 文件")  # 如果没有 .ts 文件，记录错误
        return

    # 根据文件名中的时间对 ts_files 进行排序
    ts_files.sort(key=lambda x: os.path.basename(x).split('.')[0])  # 按时间排序

    file_list_path = os.path.join(output_dir, 'filelist.txt')  # 创建文件列表路径
    
    # 检查文件是否存在
    missing_files = []  # 用于存储缺失的文件
    for ts_file in ts_files:
        if not os.path.exists(ts_file):
            #logging.error(f"文件不存在: {ts_file}")  # 如果文件不存在，记录错误
            missing_files.append(ts_file)  # 添加到缺失文件列表

    # 如果有缺失的文件，重新记录 ts_deposit
    if missing_files:
        logging.info("重新记录 ts_deposit 中的文件")  # 记录信息
        ts_deposit_dir = os.path.join(output_dir, 'ts_deposit')  # 指定 ts_deposit 目录
        ts_files = get_ts_files(ts_deposit_dir)  # 使用 ts_deposit 目录获取 ts 文件
        if not ts_files:
            logging.error("没有可用的 .ts 文件进行合成")  # 如果没有可用的文件，记录错误
            return

    with open(file_list_path, 'w') as f:
        for ts_file in ts_files:
            f.write(f"file '{ts_file}'\n")  # 将可用的 .ts 文件路径写入文件
            #logging.info(f"写入文件路径到 filelist.txt: {ts_file}")  # 记录写入信息

    # 使用第一个 .ts 文件的时间作为 .mp4 文件名
    first_ts_file_time = os.path.basename(ts_files[0]).split('.')[0]
    output_file = os.path.join(output_dir, f"{first_ts_file_time}.MP4")
    
    # 使用 ffmpeg 的 -c copy 选项来直接复制视频流，不进行解码和重新编码
    result = subprocess.run([
        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', file_list_path,
        '-c', 'copy', output_file
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        logging.error(f"FFmpeg 合成失败: {result.stderr}")
    else:
        # 检查合成文件大小
        file_size_kb = os.path.getsize(output_file) / 1024  # 转换为KB
        if file_size_kb < record_min_size:
            logging.info(f"合成文件 {output_file} 大小为 {file_size_kb}KB，小于 {record_min_size}KB，已删除")
            os.remove(output_file)
        else:
            logging.info(f"合成成功: {output_file}，大小为 {file_size_kb}KB")
            # 生成图片
            image_file = output_file.replace('.MP4', '.JPG')
            ffmpeg_image_command = [
                'ffmpeg', '-i', output_file, '-ss', '00:00:01', '-frames:v', '1', image_file
            ]
            subprocess.run(ffmpeg_image_command)
            logging.info(f"生成图片: {image_file}")

            # 计算录制的开始时间、结束时间和录制时长
            start_time = int(os.path.getmtime(ts_files[0])) - 3  # 第一个 .ts 文件的修改时间作为开始时间，前移3秒
            end_time = int(os.path.getmtime(ts_files[-1]))  # 最后一个 .ts 文件的修改时间作为结束时间
            
            # 计算录制时长
            record_duration = (end_time - start_time)  # 录制时长（秒）
            
            # 调用保存元数据的函数
            save_recording_metadata(output_file, start_time, end_time, record_duration, file_size_kb * 1024, 'MP4', camera_id, camera_group)
    
    for ts_file in ts_files:
        os.remove(ts_file)
    
    # 清除 filelist.txt
    os.remove(file_list_path)

def save_recording_metadata(video_path, start_time, end_time, record_duration, file_size, file_type, camera_id, camera_group):
    mac_address = get_mac_address()  # 确保这个函数能够返回正确格式的 MAC 地址
    # 构建包含 MAC 地址和摄像头组 ID 的保存路径
    video_filename = os.path.basename(video_path)
    save_path = f"/stt-cctv/cs/{mac_address}/{camera_group}FireDoor/{video_filename}"  # 在路径中包含文件名
    avatar_path = f"{save_path.replace('.MP4', '.JPG')}"  # 构建图片文件的路径

    metadata = {
        "list": [{
            "eventType": "AlarmFireDoorOpen",
            "cmdId": "1",
            "eventTime": int(start_time * 1000),
            "content": {
                "startTime": int(start_time * 1000),  # 转换为毫秒级时间戳
                "endTime": int(end_time * 1000),  # 转换为毫秒级时间戳
                "recordDuration": record_duration,  # 录制时长
                "fileSize": file_size,  # 文件大小
                "fileType": file_type,  # 文件类型
                "cameraId": camera_id,  # cameraId 参数
                "savePath": save_path,  # 更新后的保存路径
                "saveType": "OSS",  # 固定的保存类型
                "avatar": avatar_path,  # 添加图片路径
                "bizType": "FireDoor"  # 防火门
            }
        }]
    }

    json_path = f'/userdata/myapp/{os.path.basename(video_path).replace(".MP4", ".json")}'
    logging.info(f"准备保存元数据到: {json_path}")  # 添加调试信息
    with open(json_path, 'w') as json_file:
        json.dump(metadata, json_file, ensure_ascii=False, indent=4)
    logging.info(f"录制元数据已保存到: {json_path}")

def get_camera_id():
    camera_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not camera_id:
        print("缺少 cameraId 参数")
        sys.exit(1)
    return camera_id

def handle_ffmpeg_error(result):
    if result.returncode != 0:
        logging.error(f"FFmpeg 合成失败: {result.stderr}")
        return False
    return True

def log_and_remove_file(file_path, reason):
    try:
        #logging.info(f"删除文件 {file_path} 原因: {reason}")
        os.remove(file_path)
    except OSError as e:
        logging.error(f"删除文件 {file_path} 失败: {e}")

#开门关门判断逻辑
def detect_and_move_changes(ts_files, ts_deposit_dir, ts_jzj_dir, threshold=30, screen_change_threshold=1):
    change_files = []
    points = [[904, 55], [1175, 47], [1193, 780], [949, 819]]  # 请替换为实际的点坐标
    cache = []  # 用于缓存 .ts 文件

    # 获取基准文件
    jzj_files = sorted([f for f in os.listdir(ts_jzj_dir) if f.endswith('.ts')])
    if not jzj_files:
        logging.error("ts_jzj 文件夹中没有基准 .ts 文件")
        return change_files

    base_file = os.path.join(ts_jzj_dir, jzj_files[0])

    if len(points) == 4:
        x, y = points[0]
        w = points[2][0] - x
        h = points[2][1] - y

        # 读取基准文件
        cap_base = cv2.VideoCapture(base_file)
        ret_base, frame_base = cap_base.read()
        cap_base.release()

        if not ret_base:
            logging.error("无法读取基准文件")
            return change_files

        # 提取门的区域并转换为灰度图像
        door_frame_base = frame_base[y:y+h, x:x+w]
        door_gray_base = cv2.cvtColor(door_frame_base, cv2.COLOR_BGR2GRAY)
        edges_base = cv2.Canny(door_gray_base, 50, 150)
        initial_edges = cv2.countNonZero(edges_base)

        for ts_file in ts_files:
            cap = cv2.VideoCapture(ts_file)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                continue

            # 提取门的区域并转换为灰度图像
            door_frame = frame[y:y+h, x:x+w]
            door_gray = cv2.cvtColor(door_frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(door_gray, 50, 150)
            num_edges = cv2.countNonZero(edges)

            # 判断门是否开关
            if num_edges < initial_edges * 0.6 or num_edges > initial_edges * 1.2:
                print(f"门是开的，文件 {ts_file}")
                # 有变化，移动文件到 ts_deposit
                os.rename(ts_file, os.path.join(ts_deposit_dir, os.path.basename(ts_file)))
                change_files.append(os.path.join(ts_deposit_dir, os.path.basename(ts_file)))
                
                # 将缓存的两个文件也移动到 ts_deposit
                for cached_file in cache:
                    os.rename(cached_file, os.path.join(ts_deposit_dir, os.path.basename(cached_file)))
                    change_files.append(os.path.join(ts_deposit_dir, os.path.basename(cached_file)))
                cache.clear()  # 清空缓存
            else:
                print(f"门是关的，文件 {ts_file}")
                # 没有变化，缓存文件
                cache.append(ts_file)
                if len(cache) > 2:
                    # 删除最先缓存的文件
                    log_and_remove_file(cache.pop(0), "缓存超过两个文件，删除最先缓存的文件")

            time.sleep(1)

    return change_files

def get_ts_files(ts_dir):
    return sorted([os.path.join(ts_dir, f) for f in os.listdir(ts_dir) if f.endswith('.ts')])

def copy_first_ts_to_jzj(ts_files_dir, ts_jzj_dir):
    # 检查 ts_jzj 文件夹是否已经存在 .ts 文件
    if not os.path.exists(ts_jzj_dir):
        os.makedirs(ts_jzj_dir)
    
    if not any(fname.endswith('.ts') for fname in os.listdir(ts_jzj_dir)):
        # 获取 ts_files 文件夹中的第一个 .ts 文件
        ts_files = get_ts_files(ts_files_dir)
        if ts_files:
            first_ts_file = ts_files[0]
            # 复制第一个 .ts 文件到 ts_jzj 文件夹
            shutil.copy(first_ts_file, ts_jzj_dir)
            logging.info(f"复制 {first_ts_file} 到 {ts_jzj_dir}")

def process_video(rtmp_url, merged_output_dir, screen_change_threshold, record_duration, record_min_size, camera_id, camera_group):
    ts_files_dir = os.path.join(merged_output_dir, 'ts_files')
    ts_deposit_dir = os.path.join(merged_output_dir, 'ts_deposit')
    ts_jzj_dir = os.path.join(merged_output_dir, 'ts_jzj')  # 新增 ts_jzj 目录
    
    os.makedirs(ts_files_dir, exist_ok=True)
    os.makedirs(ts_deposit_dir, exist_ok=True)
    os.makedirs(ts_jzj_dir, exist_ok=True)  # 确保 ts_jzj 目录存在

    ffmpeg_thread = threading.Thread(target=start_ffmpeg_recording, args=(rtmp_url, ts_files_dir))
    ffmpeg_thread.start()

    # 等待第一个 .ts 文件生成
    while not get_ts_files(ts_files_dir):
        time.sleep(1)

    # 在第一个 .ts 文件生成后复制到 ts_jzj
    copy_first_ts_to_jzj(ts_files_dir, ts_jzj_dir)

    collected_changes = []  # 存储检测到变化的文件
    no_change_count = 0  # 计数连续没有变化的文件

    while True:
        try:
            ts_files = get_ts_files(ts_files_dir)

            while len(ts_files) < 2:
                time.sleep(1)
                ts_files = get_ts_files(ts_files_dir)

            ts_files_with_changes = detect_and_move_changes(ts_files, ts_deposit_dir, ts_jzj_dir, threshold=30, screen_change_threshold=screen_change_threshold)
            
            if ts_files_with_changes:
                collected_changes.extend(ts_files_with_changes)
                no_change_count = 0  # 重置计数器
            else:
                no_change_count += 1  # 增加计数器

            # 当收集到的变化文件数量达到 record_duration 时，进行合并
            if len(collected_changes) >= record_duration:
                combine_ts_to_mp4(collected_changes[:record_duration], merged_output_dir, record_min_size, camera_id, camera_group)
                collected_changes = collected_changes[record_duration:]  # 移除已合并的文件
            elif no_change_count >= 15:
                # 如果连续15个文件没有变化，删除 ts_deposit 下的文件
                ts_deposit_files = get_ts_files(ts_deposit_dir)
                for ts_file in ts_deposit_files:
                    log_and_remove_file(ts_file, "连续15个文件没有变化，删除")
                no_change_count = 0  # 重置计数器

            time.sleep(2)
        except FileNotFoundError as e:
            # 注释掉错误日志记录
            # logging.error(f"文件未找到: {e}")
            pass
        except Exception as e:
            logging.error(f"处理视频时发生错误: {e}")

# 添加一个函数来清除日志文件
def clear_log_if_necessary(log_file_path, max_size_mb=10):
    if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > max_size_mb * 1024 * 1024:
        with open(log_file_path, 'w') as log_file:
            log_file.truncate()
        logging.info("日志文件已清空，因为其大小超过了10MB")

# 添加一个函数来清空指定目录
def clear_directory_if_exists(directory_path):
    if os.path.exists(directory_path):
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logging.error(f'删除 {file_path} 失败: {e}')

def process_camera_stream(camera_id):
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
            config_data = next((item for item in config["config"] if item["cameraId"] == camera_id), None)
            if config_data:
                userName = config_data['userName']
                password = config_data['password']
                ip_address = config_data['ip']
                camera_group = config_data['cameraId']
                screen_change_threshold = int(config_data['screenChangeThreshold'])
                record_duration = int(config_data['recordDuration'])
                record_min_size = int(config_data['recordMinSize']) * 1024  # kb
                output_dir = '/userdata/'

                merged_output_dir, rtmp_url = set_output_dir_and_url(userName, password, ip_address, camera_group, output_dir)

                # 清空 ts_files 和 ts_deposit 目录
                ts_files_dir = os.path.join(merged_output_dir, 'ts_files')
                ts_deposit_dir = os.path.join(merged_output_dir, 'ts_deposit')
                clear_directory_if_exists(ts_files_dir)
                clear_directory_if_exists(ts_deposit_dir)

                process_video(rtmp_url, merged_output_dir, screen_change_threshold, record_duration, record_min_size, camera_id, camera_group)

                # 检查并清理日志文件
                log_file_path = os.path.join(base_dir, 'video_stream.log')
                clear_log_if_necessary(log_file_path)
            else:
                logging.error(f"未找到 cameraId {camera_id} 的配置")
                sys.exit(1)
    
    except Exception as e:
        logging.error(f"发生错误: {e}")
        sys.exit(1)
