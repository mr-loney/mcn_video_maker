import yt_dlp  # 需要安装 yt-dlp
import os
import json
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor
import logging
import subprocess
from mutagen.mp4 import MP4
from feishu import FeiShuDoc
from pathlib import Path
import sys
import yaml
import platform

# 拿到 "tiktok-tools" 绝对路径
tools_path = os.path.join(os.path.dirname(__file__), "tiktok-tools")
if tools_path not in sys.path:
    sys.path.append(tools_path)
import chrome_utils
import start
import bit_api

# 运行应用
if __name__ == "__main__":
    chrome_utils.test_driver_internal()