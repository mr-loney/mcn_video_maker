import time
import threading
import sys
import os
import json
import shutil

api_key_config = {
    "aliyun": {
        "access_key": "LTAI5tB5H482ggkTeZRvUpXu",
        "accecss_secret": "xveXIqfEUEvSbtEQQDDK8ZsKkdsedt",
        "appkey": "5W6eeld6u10hUEHx"
    },
    "huoshan": {
        "access_token": "FOKHbIJNtqpF_1Ebwc6gEuXbToedHxCp",
        "appid": "7930767699"
    },
    "ali_dashscope": {
        "api-key": "sk-25f4c933079e4505a477c892d3d3b5cf"
    }
}

thisFileDir = os.path.dirname(os.path.abspath(__file__))
def get_config(rt, key):
    return api_key_config[rt][key]
    
def generate_key(string):
    import hashlib
    md5 = hashlib.md5()
    encoded_string = string.encode('utf-8')
    md5.update(encoded_string)
    key = md5.hexdigest()
    return key

def tempDir():
    tmpdir = os.path.join(thisFileDir, ".temp")
    if os.path.exists(tmpdir) == False:
        os.makedirs(tmpdir)
    return tmpdir

def claerCache():
    tmpdir = tempDir()
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    imageCacheDir = os.path.join(thisFileDir, "template2", ".images")
    if os.path.exists(imageCacheDir):
        shutil.rmtree(imageCacheDir)
    
def cache_data(cate, string):
    k = generate_key(string)
    if os.path.exists(os.path.join(tempDir(), f"{cate}_{k}")):
        with open(os.path.join(tempDir(), f"{cate}_{k}"), "r") as f:
            return f.read()
    return None

def save_cache(cate, string, data):
    k = generate_key(string)
    with open(os.path.join(tempDir(), f"{cate}_{k}"), "w") as f:
        f.write(data)
    pass

def _randomize_uuid_format(s):
    import random
    import string
    def random_digits(n):
        return ''.join(random.choices(string.digits, k=n))
    
    def random_hex(n):
        return ''.join(random.choices('0123456789abcdef', k=n))
    
    parts = s.split('-')
    new_parts = []
    
    for part in parts:
        if any(c in string.ascii_letters for c in part):
            new_part = random_hex(len(part))
        else:
            new_part = random_digits(len(part))
        new_parts.append(new_part)
    
    new_s = '-'.join(new_parts)
    return new_s

def updateVideoMeta(video_path):
    from mutagen.easymp4 import MP4, EasyMP4, EasyMP4Tags
    videoId = _randomize_uuid_format("98399511-2a08-4044-b672-8b77224cada4")
    md = {
        "data": {
            "infoStickerId": "7233739460242885893,7233769760033737990",
            "is_use_ai_translation": 0,
            "is_use_relight": 0,
            "is_use_voice_clone": "0",
            "is_use_voice_optimization": 0,
            "motion_blur_cnt": 0,
            "musicId": "",
            "os": "mac",
            "product": "vicut",
            "stickerId": "",
            "videoEffectId": "",
            "videoId": videoId,
            "videoParams": {
                "be": 0,
                "ef": 0,
                "ft": 0,
                "ma": 0,
                "me": 0,
                "mu": 0,
                "re": 0,
                "sp": 0,
                "st": 8,
                "te": 0,
                "tx": 0,
                "v": 0,
                "vs": 0
            }
        },
        "source_type": "vicut"
    }
    md_json = json.dumps(md)
    file = EasyMP4(video_path)
    # EasyMP4Tags.RegisterFreeformKey("Format_Profile", "Format_Profile")
    # file['Format_Profile'] = "QuickTime"
    # EasyMP4Tags.RegisterTextKey("CodecID", "qt")
    # EasyMP4Tags.RegisterTextKey("CodecID_Compatible", "qt")
    # EasyMP4Tags.RegisterFreeformKey("Encoded_Library", "Encoded_Library")
    # file['Encoded_Library'] = "Apple QuickTime"
    # EasyMP4Tags.RegisterFreeformKey("Encoded_Library_Name", "Encoded_Library_Name")
    # file['Encoded_Library_Name'] = "Apple QuickTime"
    EasyMP4Tags.RegisterFreeformKey("com.apple.quicktime.artwork", "com.apple.quicktime.artwork")
    file['com.apple.quicktime.artwork'] = md_json
    file.save()