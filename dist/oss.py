import os
import time
import oss2
from tqdm import tqdm

# 本地文件夹路径目录
basedir_sp = '/media/monster/数据/sp'

bucket = 'stt-cctv'
# 将accessKeyId 和 accessKeySecret
ossAuth = oss2.Auth('1', '1')
# 使用正确的端点
ossBucket = oss2.Bucket(ossAuth, 'http://oss-cn-hongkong.aliyuncs.com', bucket)

# 记录文件的最后修改时间
file_mod_times = {}

def sanitize_path(path):
    # 替换不允许的字符并移除开头的斜杠
    return path.replace(':', '_').lstrip('/')

def uploadFile2Oss(local_dir):
    print(f'>>>>>>>>>Upload from: {local_dir} --- Start!')
    listFile(local_dir, local_dir)

def uploadFile(file, basedir):
    # 路径
    relative_path = os.path.relpath(file, basedir)
    sanitized_file = sanitize_path(relative_path)
    remoteName = os.path.join(sanitized_file).replace('\\', '/')
    print('uploading..', file, 'remoteName', remoteName)
    
    # 获取文件大小
    file_size = os.path.getsize(file)
    
    # 定义进度回调函数
    def progress_callback(consumed_bytes, total_bytes):
        progress_bar.update(consumed_bytes - progress_bar.n)
    
    # 创建进度条
    with tqdm(total=file_size, unit='B', unit_scale=True, desc=file) as progress_bar:
        try:
            result = ossBucket.put_object_from_file(remoteName, file, progress_callback=progress_callback)
            # 文件上传成功http状态输出200
            print('http status: {0}'.format(result.status))
        except oss2.exceptions.OssError as e:
            print(f'Error uploading {file}: {e}')

def listFile(dir, basedir):
    fs = os.listdir(dir)
    for f in fs:
        file = os.path.join(dir, f)
        if os.path.isdir(file):
            listFile(file, basedir)
        else:
            # 检查文件是否有变化
            mod_time = os.path.getmtime(file)
            if file not in file_mod_times or file_mod_times[file] != mod_time:
                file_mod_times[file] = mod_time
                uploadFile(file, basedir)

if __name__ == '__main__':
    # 填写本地路径
    local_dir = basedir_sp
    while True:
        uploadFile2Oss(local_dir)
        # 每隔60秒检查一次
        time.sleep(60)
