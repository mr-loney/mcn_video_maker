import oss2
import requests
import os
import hashlib
from datetime import datetime

# 填写RAM用户的访问密钥（AccessKey ID和AccessKey Secret）。
accessKeyId = 'LTAI5tC7E3DrmtGsXN4dSKef'
accessKeySecret = '0Imeg0eYisOok5zZpi9rJj8Vs6yZxu'
# 使用代码嵌入的RAM用户的访问密钥配置访问凭证。
auth = oss2.Auth(accessKeyId, accessKeySecret)
bucket = oss2.Bucket(auth, 'https://oss-cn-hongkong.aliyuncs.com', 'vooskymedia')
bucket2 = oss2.Bucket(auth, 'https://oss-cn-shenzhen.aliyuncs.com', 'cftask')

# 计算文件路径的唯一哈希值
def generate_unique_hash(path):
    # 使用 SHA-256 算法来生成哈希值
    hash_object = hashlib.sha256(path.encode())
    # 获取哈希值的十六进制表示
    hash_hex = hash_object.hexdigest()
    return hash_hex

# 获取文件的后缀
def get_file_extension(path):
    _, extension = os.path.splitext(path)
    return extension

# 生成新的文件名
def generate_new_filename(path):
    # 生成唯一哈希值
    unique_hash = generate_unique_hash(path)
    # 获取文件后缀
    extension = get_file_extension(path)
    # 组合新的文件名
    new_filename = unique_hash + extension
    return new_filename

def loadURL(filepath):
    # 必须以二进制的方式打开文件。
    # 填写本地文件的完整路径。如果未指定本地路径，则默认从示例程序所属项目对应本地路径中上传文件。
    # filename = os.path.basename(filepath)
    filename = generate_new_filename(filepath)
    with open(filepath, 'rb') as fileobj:
        # Seek方法用于指定从第1000个字节位置开始读写。上传时会从您指定的第1000个字节位置开始上传，直到文件结束。
        fileobj.seek(0, os.SEEK_SET)
        # Tell方法用于返回当前位置。
        current = fileobj.tell()
        # 填写Object完整路径。Object完整路径中不能包含Bucket名称。
        bucket.put_object(filename, fileobj)
    return 'https://vooskymedia.oss-cn-hongkong.aliyuncs.com/' + filename

def loadURLtoCN(filepath):
    # 必须以二进制的方式打开文件。
    # 填写本地文件的完整路径。如果未指定本地路径，则默认从示例程序所属项目对应本地路径中上传文件。
    
    filename = os.path.basename(filepath)
    name, extension = os.path.splitext(filename)
    current_timestamp_ms = int(datetime.now().timestamp() * 1000)
    data_key = name + str(current_timestamp_ms)
    filename = hashlib.md5(data_key.encode('utf-8')).hexdigest() + extension
    with open(filepath, 'rb') as fileobj:
        # Seek方法用于指定从第1000个字节位置开始读写。上传时会从您指定的第1000个字节位置开始上传，直到文件结束。
        fileobj.seek(0, os.SEEK_SET)
        # Tell方法用于返回当前位置。
        current = fileobj.tell()
        # 填写Object完整路径。Object完整路径中不能包含Bucket名称。
        bucket2.put_object(filename, fileobj)
    return 'https://cftask.oss-cn-shenzhen.aliyuncs.com/' + filename