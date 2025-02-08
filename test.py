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

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

required_fields = {
            "port": 7890,
            "socks-port": 7891,
            "allow-lan": False,
            "log-level": "info",
            "external-controller": "127.0.0.1:9090",
            "secret": "517DE8FBC646FEAD84A5CC1432A578F2"
        }

required_fields2 = {
    "port": 7890,
    "socks-port": 7891,
    "allow-lan": False,
    "mode": "Global",  # 这里可选 "Global" or "Rule"
    "log-level": "info",
    "external-controller": "127.0.0.1:9090",
    "secret": "517DE8FBC646FEAD84A5CC1432A578F2",
    "unified-delay": True,
    "hosts": {
        "time.facebook.com": "17.253.84.125",
        "time.android.com": "17.253.84.125"
    },
    "dns": {
        "enable": True,
        "use-hosts": True,
        "nameserver": [
            "119.29.29.29",
            "223.5.5.5",
            "223.6.6.6",
            "tcp://223.5.5.5",
            "tcp://223.6.6.6",
            "tls://dns.google:853",
            "tls://8.8.8.8:853",
            "tls://8.8.4.4:853",
            "tls://dns.alidns.com",
            "tls://223.5.5.5",
            "tls://223.6.6.6",
            "tls://dot.pub",
            "tls://1.12.12.12",
            "tls://120.53.53.53",
            "https://dns.google/dns-query",
            "https://8.8.8.8/dns-query",
            "https://8.8.4.4/dns-query",
            "https://dns.alidns.com/dns-query",
            "https://223.5.5.5/dns-query",
            "https://223.6.6.6/dns-query",
            "https://doh.pub/dns-query",
            "https://1.12.12.12/dns-query",
            "https://120.53.53.53/dns-query"
        ],
        "default-nameserver": [
            "119.29.29.29",
            "223.5.5.5",
            "223.6.6.6",
            "tcp://119.29.29.29",
            "tcp://223.5.5.5",
            "tcp://223.6.6.6"
        ]
    }
}

def switch_clash_mode(mode_value):
    """
    mode_value: "Rule", "Global", "direct"...
    """
    clash_api_url = "http://127.0.0.1:9090"
    clash_token   = "517DE8FBC646FEAD84A5CC1432A578F2"
    headers = {"Authorization": f"Bearer {clash_token}"}

    try:
        url = f"{clash_api_url}/configs"
        data = {"mode": mode_value}
        r = requests.patch(url, headers=headers, json=data, timeout=5)
        if r.status_code == 204:
            logger.info(f"成功切换Clash为 {mode_value} 模式!")
        else:
            logger.error(f"切换Clash模式失败: code={r.status_code}, resp={r.text}")
    except Exception as e:
        logger.error(f"切换Clash模式异常: {e}")
    
    if mode_value == "Global":
        switch_clash_global()

def switch_clash_global():
    """
    mode_value: "Rule", "Global", "direct"...
    """
    clash_api_url = "http://127.0.0.1:9090"
    clash_token   = "517DE8FBC646FEAD84A5CC1432A578F2"
    headers = {"Authorization": f"Bearer {clash_token}"}

    try:
        url = f"{clash_api_url}/proxies/GLOBAL"
        data = {"name": "🔰 节点选择"}
        r = requests.put(url, headers=headers, json=data, timeout=5)
        if r.status_code == 204:
            logger.info(f"成功切换GLOBAL为 🔰 节点选择")
        else:
            logger.error(f"切换GLOBAL失败: code={r.status_code}, resp={r.text}")
    except Exception as e:
        logger.error(f"切换GLOBAL异常: {e}")

def switch_clash_profile(config_name):
    """
    将 Clash 整体切换到新的配置文件(而不是切换分组节点)。
    比如 config_name="A1" -> 加载 /Users/xxx/.config/clash/A1.yaml
    """
    clash_api_url = "http://127.0.0.1:9090"
    clash_token   = "517DE8FBC646FEAD84A5CC1432A578F2"  # 视具体情况
    headers = {
        "Authorization": f"Bearer {clash_token}"
    }

    home_dir = Path.home()  # 跨平台获取用户主目录
    config_dir = home_dir / ".config" / "clash"
    config_path = str(config_dir / f"{config_name}.yaml")

    # 先修正/补齐指定字段
    if config_name == "root":
        ensure_clash_config_fields(config_path, required_fields)
    else:
        ensure_clash_config_fields(config_path, required_fields2)

    try:
        url = f"{clash_api_url}/configs?force=true"
        data = {"path": config_path, "GLOBAL": "🔰 节点选择"}

        resp = requests.put(url, headers=headers, json=data, timeout=5)
        if resp.status_code == 204:
            logger.info(f"成功将 Clash 整体切换为配置 {config_name}")
        else:
            logger.error(f"切换配置失败: {resp.status_code}, resp={resp.text}")
    except Exception as e:
        logger.error(f"切换配置时异常: {e}")

def ensure_clash_config_fields(yaml_path: str, required_data: dict):
    """
    读取 yaml_path => 加/改 required_data 里的字段 => 覆盖写回
    """
    if not os.path.isfile(yaml_path):
        # 文件不存在 => 新建一个空字典
        current = {}
    else:
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                current = yaml.safe_load(f)
            if not isinstance(current, dict):
                current = {}
        except:
            current = {}

    # 递归合并
    merged = merge_dicts_required(current, required_data)

    # 写回
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(merged, f, sort_keys=False, allow_unicode=True)

def merge_dicts_required(orig: dict, required: dict) -> dict:
    """
    对 required 里的字段进行递归覆盖:
    - 如果 orig 不存在此 key, 则添加
    - 如果 orig 存在, 但 required[key] 是 dict => 递归进入
    - 如果 orig 存在, 但 required[key] 不是 dict => 强制覆盖
    """
    for key, val in required.items():
        if isinstance(val, dict):
            if key not in orig or not isinstance(orig.get(key), dict):
                orig[key] = {}
            merge_dicts_required(orig[key], val)
        else:
            # 直接覆盖
            orig[key] = val
    return orig

if __name__ == "__main__":
    switch_clash_mode("Global")
    switch_clash_profile("A4")