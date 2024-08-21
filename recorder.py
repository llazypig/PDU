import os
import time
import oss2
from tqdm import tqdm

# 本地文件夹路径目录
basedir = '/home/monster/Desktop/share/DCIM/hc'
# 阿里云存储目录，要保证和下面的project_name相同
projectList = ['b-cctv/']
# 本地文件夹
dirList = [basedir]

bucket = 'stt-cctv'  # 设置为你的存储桶名称
ossDir = 'b-cctv/'  # 替换为你实际的目录
# 将accessKeyId 和 accessKeySecret替换自己的
ossAuth = oss2.Auth('yourAccessKeyId', 'yourAccessKeySecret')
# 使用正确的端点
ossBucket = oss2.Bucket(ossAuth, 'http://oss-cn-hongkong.aliyuncs.com', bucket)

# 记录文件的最后修改时间
file_mod_times = {}

def uploadFile2Oss(pro):
    if pro in projectList:
        print('>>>>>>>>>Upload:' + pro + '---Start!')
        global ossDir, basedir, bucket, ossBucket
        ossDir, basedir = pro, dirList[projectList.index(pro)]
        listFile(basedir)
    else:
        print('请检查填写的bucket名称和地址是否正确')

def uploadFile(file):
    # remoteName为oss目录名称, file为本地上传目录名称
    remoteName = ossDir + file.replace(basedir, '').replace('\\', '/')
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

def listFile(dir):
    fs = os.listdir(dir)
    for f in fs:
        file = os.path.join(dir, f)
        if os.path.isdir(file):
            listFile(file)
        else:
            # 检查文件是否有变化
            mod_time = os.path.getmtime(file)
            if file not in file_mod_times or file_mod_times[file] != mod_time:
                file_mod_times[file] = mod_time
                uploadFile(file)

if __name__ == '__main__':
    # 填写oss的存储路径
    project_name = 'b-cctv/'
    while True:
        uploadFile2Oss(project_name)
        # 每隔60秒检查一次
        time.sleep(60)
