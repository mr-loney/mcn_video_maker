import yt_dlp  # 需要安装 yt-dlp
import os
import json
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
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

import start
import bit_api

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def get_ffmpeg_path():
    # 检测当前操作系统
    system_name = platform.system()

    if hasattr(sys, '_MEIPASS'):
        # 在 PyInstaller 打包环境下
        if system_name == "Windows":
            return os.path.join(sys._MEIPASS, 'ffmpeg', 'ffmpeg.exe')
        else:
            return os.path.join(sys._MEIPASS, 'ffmpeg', 'ffmpeg')
    else:
        # 未打包时，使用系统已安装的 ffmpeg
        # 如果在 Windows 下，常见可执行文件是 ffmpeg.exe
        # 如果在 macOS/Linux 下，则是 ffmpeg
        if system_name == "Windows":
            return 'ffmpeg.exe'
        else:
            return 'ffmpeg'

ffmpeg_path = get_ffmpeg_path()

def get_aria2c_path():
    # 检测当前操作系统
    system_name = platform.system()

    if hasattr(sys, '_MEIPASS'):
        # 在 PyInstaller 打包环境下
        if system_name == "Windows":
            return os.path.join(sys._MEIPASS, 'aria2c', 'aria2c.exe')
        else:
            return os.path.join(sys._MEIPASS, 'aria2c', 'aria2c')
    else:
        # 未打包时，使用系统已安装的 aria2c
        if system_name == "Windows":
            return 'aria2c.exe'  # 确保 aria2c.exe 在系统的 PATH 环境变量中
        else:
            return 'aria2c'  # 确保 aria2c 在系统的 PATH 环境变量中

aria2c_path = get_aria2c_path()

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

class CheckWebUpdates:
    def __init__(self, watch_folders, main_app_path, max_concurrent_downloads=4):
        """
        :param watch_folders: 要监控的子文件夹列表(如 ["folder1", "folder2", ...])
        :param main_app_path: 主应用路径，用于存放 checkweb.json
        :param max_concurrent_downloads: 最大并发下载数
        """
        self.is_listening = False
        self.watch_folders = watch_folders
        self.folder_path = ""  # 父文件夹路径，通过 update_list 来设定
        self.main_app_path = main_app_path
        self.max_concurrent_downloads = max_concurrent_downloads

        # checkweb.json 的绝对路径 => 记录 { folder: last_weburl }
        self.checkweb_json_file = os.path.join(self.main_app_path, "checkweb.json")
        self.ket_json_file = os.path.join(self.main_app_path, "key.json")

        # 读取本地记录(如果文件不存在/损坏 => 空字典)
        self.last_video_urls = self.load_checkweb_json()
        self.load_key()

        # 这里定义你想强制的字段(如port, socks-port等):
        # 若你需要更多 dns/default-nameserver，继续补充
        self.required_fields = {
            "port": 7890,
            "socks-port": 7891,
            "allow-lan": False,
            "log-level": "info",
            "external-controller": "127.0.0.1:9090",
            "secret": "517DE8FBC646FEAD84A5CC1432A578F2"
        }

        self.required_fields2 = {
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
    
    def load_key(self):
        if os.path.exists(self.ket_json_file):
            try:
                with open(self.ket_json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    sf_intent = FeiShuDoc()
                    is_success = sf_intent.get_key(data["key"])
                    if is_success:
                        print("鉴权成功,欢迎使用MCN伴侣!")
                    else:
                        self.sysexit()
                else:
                    self.sysexit()
            except Exception as e:
                self.sysexit()
        else:
            self.sysexit()

    def sysexit(self):
        print("鉴权失败,内测期间不闪退,请尽快激活key.json")
        # sys.exit()

    def load_checkweb_json(self):
        """从 checkweb.json 加载 last_video_urls 记录(存储 form: { folder: 'https://youtube.com/watch?v=xxx', ... })"""
        if os.path.exists(self.checkweb_json_file):
            try:
                with open(self.checkweb_json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
                else:
                    logger.warning("checkweb.json 不是一个 dict，忽略并视为空.")
                    return {}
            except Exception as e:
                logger.error(f"读取 checkweb.json 出错: {e}, 视为空.")
                return {}
        else:
            return {}

    def save_checkweb_json(self):
        """将 last_video_urls 写入 checkweb.json"""
        try:
            with open(self.checkweb_json_file, "w", encoding="utf-8") as f:
                json.dump(self.last_video_urls, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"写入 checkweb.json 出错: {e}")

    def check_new_videos(self):
        """
        并行地（最多 3 个线程）检查 self.watch_folders 下每个文件夹的 config.json => sub_link => 是否有新视频
        """
        # 准备一个任务列表
        tasks = []
        
        # 创建最多 3 个线程的 ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as executor:
            for folder in self.watch_folders:
                config_file = os.path.join(self.folder_path, folder, 'config.json')
                # 如果 config_file 不存在，就跳过
                if not os.path.exists(config_file):
                    continue

                # 定义一个针对“单个 folder”的任务函数
                def check_folder(folder_path, config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as file:
                            config = json.load(file)
                        sub_link = config.get('sub_link', '')
                        if sub_link:
                            self.check_sub_link(sub_link, folder_path)
                    except json.JSONDecodeError:
                        logger.error(f"无法读取 {config_path} 文件，可能不是有效的JSON文件")
                    except Exception as e:
                        logger.error(f"检查文件夹 {folder_path} 时发生错误: {e}")

                # 提交任务到线程池
                future = executor.submit(check_folder, folder, config_file)
                tasks.append(future)

            # 可选：如果需要在所有任务完成后再做进一步处理，可以在这里等待:
            for future in as_completed(tasks):
                # 如有需要，可获取 future.result()
                # 如果执行过程中抛了异常，会在这里 re-raise
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"子线程任务出现异常: {e}")

    def check_sub_link(self, sub_link, folder):
        """
        检查某个文件夹 folder 的 YouTube 订阅链接 sub_link 是否有更新,
        如果有 => 记录最新 weburl => 下载视频 => 更新 checkweb.json
        """
        try:
            # 使用 yt-dlp 获取最新视频ID (extract_flat=True)
            ydl_opts = {
                'quiet': True,         # 静默模式
                'extract_flat': True   # 只提取视频信息 => entries[] => [ { 'id': 'xxx', ...}, ... ]
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(sub_link, download=False)
                entries = info_dict.get('entries', [])
                if not entries:
                    logger.info(f"文件夹 {folder} => sub_link: {sub_link}, 没有找到视频 (列表为空)")
                    return

            # 遍历 entries，跳过会员限定视频
            latest_video_id = None
            latest_video_title = ""
            for video_info in entries:
                # 判断可用性:
                # yt-dlp 通常在 'availability' 字段或 'membership' 字段中标识会员视频
                # 例如 'availability': 'needs_subscription'
                # 这里演示：若有 "availability" 为 "needs_subscription" 或 "needs_membership" ，就跳过
                if video_info.get('availability') in ('subscriber_only', 'needs_subscription', 'needs_membership'):
                    # logger.info(f"跳过会员视频: {video_info.get('title')}")
                    continue

                # 如果不是会员视频 => 就使用它做“最新”
                latest_video_id = video_info.get('id')
                latest_video_title = video_info.get('title', '')
                break  # 只要“最新可用”的就跳出

            if not latest_video_id:
                # 如果整份列表都跳过了（都是会员视频），则不更新
                logger.info(f"文件夹 {folder}: 全部视频均需会员，跳过更新")
                return
        
            # 获取此 ID 对应的 "weburl"
            web_url = self.get_video_download_url(latest_video_id)

            # 取旧记录
            old_web_url = self.last_video_urls.get(folder)
            # old_web_url = "debug"

            # 如果 old_web_url 不存在 => 首次 => 不算更新, 写入
            if not old_web_url:
                logger.info(f"文件夹 {folder} => 记录最新URL => {web_url}")
                self.last_video_urls[folder] = web_url
                self.save_checkweb_json()
                return

            # 若 old_web_url != new => 有更新，启动下载
            if old_web_url != web_url:
                logger.info(f"文件夹 {folder} => 检测到新视频!")
                logger.info(f"最新视频URL: {web_url}")
                logger.info("开始分析并下载多个视频...")

                # 开始并行下载最多指定数目的视频
                with ThreadPoolExecutor(max_workers=self.max_concurrent_downloads) as executor:
                    executor.submit(self.download_video, sub_link, folder, web_url, latest_video_title)

                logger.info("下载完成!")
                # 更新 checkweb.json
                self.last_video_urls[folder] = web_url
                self.save_checkweb_json()
            else:
                logger.info(f"文件夹 {folder} => 无需更新URL => {old_web_url}")

        except Exception as e:
            logger.error(f"检查 {folder} ({sub_link}) 时发生错误: {e}")

    def download_video(self, sub_link, folder, web_url, latest_video_title):
        """模拟下载视频并保存到指定路径"""
        try:
            # If we have a non-empty latest_video_title, let's write it back to config.json
            if latest_video_title:
                config_path = os.path.join(self.folder_path, folder, "config.json")
                if os.path.isfile(config_path):
                    try:
                        with open(config_path, "r", encoding="utf-8") as cf:
                            cfg_data = json.load(cf)
                        # Overwrite "tiktok_title"
                        cfg_data["tiktok_title"] = latest_video_title
                        with open(config_path, "w", encoding="utf-8") as cf:
                            json.dump(cfg_data, cf, ensure_ascii=False, indent=4)
                        logger.info(f"已将最新视频标题写入 config.json => tiktok_title = {latest_video_title}")
                    except json.JSONDecodeError:
                        logger.warning(f"无法读取或解析 {config_path}，跳过标题写入。")

            logger.info(f"开始下载视频 {web_url} 到文件夹 {folder}/output/download.mp4")

            # 调用 self.res_find_url 获得真实的下载链接
            download_url = self.res_find_url(web_url)
            if download_url:
                logger.info(f"开始从 {download_url} 下载...")
                output_folder = os.path.join(self.folder_path, folder, "output")
                os.makedirs(output_folder, exist_ok=True)
                result_file = os.path.join(output_folder, "download.mp4")
                
                # 使用 aria2c 来下载视频
                try:
                    # 设置 aria2c 下载命令
                    aria2c_command = [
                        get_aria2c_path(), # aria2c 命令
                        "--continue=true", # 启用断点续传
                        "--max-connection-per-server=4", # 每个服务器最大连接数
                        "--split=4",       # 将文件分为 4 个部分下载
                        "--out", "download.mp4",  # 指定输出文件路径
                        download_url       # 下载 URL
                    ]

                    # 启动 aria2c 下载
                    subprocess.run(aria2c_command, check=True, cwd=output_folder)
                    logger.info(f"视频下载完成并保存为 {result_file}")
                
                except subprocess.CalledProcessError as e:
                    logger.error(f"下载过程中发生错误: {e}")
                    return

                # 获取视频时长
                video_duration = self.get_video_duration(result_file)

                # 根据视频时长切割视频
                if video_duration <= 5 * 60:
                    logger.info("视频时长小于5分钟，不进行切割")

                    # 先定义一个临时文件名
                    temp_file = os.path.join(output_folder, "temp_1.mp4")

                    # 在这里先cut_video到临时文件
                    self.cut_video(result_file, temp_file, 0, video_duration, latest_video_title, " ")

                    # 再重命名 temp_1.mp4 => result.mp4
                    final_name = os.path.join(output_folder, "result.mp4")
                    if os.path.exists(final_name):
                        os.remove(final_name)
                    os.rename(temp_file, final_name)

                    # 删除原始下载文件
                    if os.path.exists(result_file):
                        os.remove(result_file)
                        logger.info(f"删除原始视频文件: {result_file}")
                    else:
                        logger.warning(f"原始视频文件不存在: {result_file}")
                else:
                    if video_duration <= 20 * 60:
                        logger.info("视频时长在5-20分钟之间，切割为3份")
                        num_parts = 3
                    else:
                        logger.info("视频时长大于20分钟，切割为5份")
                        num_parts = 5

                    segment_duration = video_duration / num_parts

                    # 用列表存储 (temp_file, final_file) => 便于最后一起 rename
                    file_pairs = []

                    for i in range(num_parts):
                        temp_file  = os.path.join(output_folder, f"temp_{i+1}.mp4")
                        final_file = os.path.join(output_folder, f"result_{i+1}.mp4")

                        # 传入 cut_video 时，第三个参数 part_label => "Part {i+1}"
                        part_label = f"Part {i+1}"
                        self.cut_video(
                            input_file=result_file,
                            output_file=temp_file,
                            start_time=i * segment_duration,
                            duration=segment_duration,
                            video_title=latest_video_title,
                            part_label=part_label
                        )

                        file_pairs.append((temp_file, final_file))

                    # 所有 cut_video 完成后，再统一 rename
                    for temp_file, final_file in file_pairs:
                        if os.path.exists(final_file):
                            os.remove(final_file)
                        os.rename(temp_file, final_file)

                    # 删除原始下载文件
                    if os.path.exists(result_file):
                        os.remove(result_file)
                        logger.info(f"删除原始视频文件: {result_file}")
                    else:
                        logger.warning(f"原始视频文件不存在: {result_file}")
            else:
                logger.warning(f"资源链接解析失败，无法下载 {web_url}")
        except Exception as e:
            logger.error(f"下载 {web_url} 时发生错误: {e}")

    def res_find_url(self, url):
        logger.info("开始解析资源url: " + url)
        params = {
            'userId': '8C1C697A1D9D3E1A891E88F5DB64F2B6',
            'secretKey': '994a4ade05d06bd5aaa105d839bbbc28',
            'url': url
        }
        self.hhm_api = 'https://h.aaaapp.cn/single_post'
        try:
            r = requests.post(self.hhm_api, json=params, verify=False).json()
            if r["code"] == 200:
                for mdata in r["data"]["medias"]:
                    if mdata["media_type"] == "video":
                        logger.info("资源url解析成功")
                        return mdata["resource_url"]
                        # if "formats" in mdata:
                        #     return mdata["formats"][0]["video_url"]
                        # else:
                        #     return mdata["resource_url"]
            else:
                logger.warning("资源url解析失败")
                return ""
        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return ""

    def get_video_download_url(self, video_id):
        """
        返回类似 'https://www.youtube.com/watch?v=xxx' 作为最新发布视频的weburl
        """
        return f"https://www.youtube.com/watch?v={video_id}"

    def update_list(self, folder_path, watch_folders):
        """外部可调用 => 更新 self.folder_path 与 watch_folders"""
        self.folder_path = folder_path
        self.watch_folders = watch_folders

    def start_checking(self):
        """每10秒检查一次"""
        while True:
            if self.is_listening:
                self.check_new_videos()
                self.scan_and_process_videos()

            time.sleep(10)
    
    def updateEventlistener(self, is_listening):
        if is_listening:
            # 清空 checkweb.json 文件
            self.clear_checkweb_json()

            self.switch_clash_mode("Rule")
            self.switch_clash_profile("root")
        self.is_listening = is_listening

    def clear_checkweb_json(self):
        """清空 checkweb.json 文件，保留值为 'debug' 的键，同时清空 last_video_urls 中值非 'debug' 的键"""
        if os.path.exists(self.checkweb_json_file):
            try:
                # 读取当前的 checkweb.json 内容
                with open(self.checkweb_json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 遍历检查每个键值对，删除值非 'debug' 的键
                keys_to_remove = [key for key, value in data.items() if value != "debug"]
                
                # 删除非 'debug' 的键值对
                for key in keys_to_remove:
                    del data[key]
                
                # 将修改后的数据写回 checkweb.json
                with open(self.checkweb_json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                
                logger.info(f"成功清空 {self.checkweb_json_file} 文件中非 'debug' 键的值.")
            except Exception as e:
                logger.error(f"清空 {self.checkweb_json_file} 文件时发生错误: {e}")
        else:
            logger.warning(f"{self.checkweb_json_file} 文件不存在.")

        # 清空 last_video_urls 中非 'debug' 的键
        keys_to_remove = [key for key, value in self.last_video_urls.items() if value != "debug"]
        
        for key in keys_to_remove:
            del self.last_video_urls[key]
        
        logger.info(f"成功清空 last_video_urls 中非 'debug' 的键.")
    
    def scan_and_process_videos(self):
        """
        扫描所有 watch_folders 下的 output/ 目录，找 result.mp4、result_1.mp4 等文件，
        并将它们加入待发送队列 => 然后执行发送。
        """
        to_send_list = []

        for folder in self.watch_folders:
            output_dir = os.path.join(self.folder_path, folder, "output")
            if not os.path.isdir(output_dir):
                continue

            # 寻找符合命名规则的文件 result*.mp4
            # 例如：result.mp4, result_1.mp4, result_2.mp4...
            mp4_files = []
            for f in os.listdir(output_dir):
                if f.startswith("result") and f.endswith(".mp4"):
                    mp4_files.append(f)
            mp4_files.sort()  # 按名称顺序保证 result.mp4, result_1.mp4, ...

            # 如果有需要发送的文件 => 生成描述txt => 加入待发送
            if mp4_files:
                # 从 config.json 读取 tiktok_title / tiktok_tags
                config_file = os.path.join(self.folder_path, folder, "config.json")
                tiktok_title, tiktok_tags, clash_id, browser_id, is_pre = self.read_config_info(config_file)

                # 如果没有配置 browser_id，则跳过该文件夹
                if not browser_id:
                    logger.warning(f"文件夹 {folder} 没有配置 browser_id，不执行发布视频逻辑!")
                    continue
                
                # 生成new txt
                txt_name = "new.txt"
                txt_path = os.path.join(output_dir, txt_name)
                
                # 写入标题/标签
                self.write_tiktok_text(txt_path, tiktok_title, tiktok_tags)
                
                for vf in mp4_files:
                    video_path = os.path.join(output_dir, vf)

                    # 加入队列
                    to_send_list.append({
                        "folder": folder,
                        "video_path": video_path,
                        "txt_path": txt_path,
                        "clash_id": clash_id if clash_id else "",
                        "browser_id": browser_id if browser_id else "",
                        "is_pre": is_pre if is_pre else "否",
                    })
        
        # 处理发送
        if to_send_list:
            self.send_videos(to_send_list)

    def read_config_info(self, config_file):
        """
        从 config.json 中读取:
         -- tiktok_title
         -- tiktok_tags
         -- clash_id (如果没有则返回 "")
         -- browser_id 指纹浏览器id
        """
        title = "Default title"
        tags  = "#fyp #viral"
        c_id  = ""
        b_id  = ""
        is_pre = "否"
        if os.path.isfile(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if "tiktok_title" in data:
                    title = data["tiktok_title"]
                if "tiktok_tags" in data:
                    tags = data["tiktok_tags"]
                if "clash_id" in data:
                    c_id = data["clash_id"]
                if "browser_id" in data:
                    b_id = data["browser_id"]
                if "is_pre" in data:
                    is_pre = data["is_pre"]
                else:
                    is_pre = "否"
            except:
                pass
        return title, tags, c_id, b_id, is_pre

    def write_tiktok_text(self, txt_path, title, tags):
        """将 tiktok_title + tiktok_tags 写到 txt 文件"""
        with open(txt_path, 'w', encoding='utf-8') as f:
            # 这里只是示例写入方式，可以自定义格式
            f.write(f"{title}\n{tags}\n")

    def send_videos(self, to_send_list):
        for item in to_send_list:
            video_path = item["video_path"]
            txt_path   = item["txt_path"]
            clash_id   = item["clash_id"]
            browser_id = item["browser_id"]
            is_pre = item["is_pre"]

            # 1) 切换clash节点 => clash API
            if clash_id:
                self.switch_clash_mode("Global")
                self.switch_clash_profile(clash_id)
                self.switch_clash_global()

            # 2) 模拟发送(3秒)
            logger.info(f"正在发送: {video_path} + {txt_path}")
            logger.info(f"指纹浏览器: {browser_id} (节点: {clash_id})")

            # 获取视频文件的上级路径和文件名
            video_root_path = os.path.dirname(video_path)
            video_name = os.path.basename(video_path)
            
            # 构造命令
            # source_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
            # command = f"python3.11 tiktok-tools/start.py --env_id={browser_id} --video_root_path={video_root_path} --video_name={video_name} --node_ip={0} --is_pre={is_pre}"
            # # 执行命令
            # try:
            #     subprocess.run(command, cwd=source_path, shell=True, check=True)
            #     print("发布成功！")
            # except subprocess.CalledProcessError as e:
            #     print(f"发布失败：{e}")
            
            start.publish_video(
                video_dir=video_root_path,
                video_name=video_name,
                browser_id=bit_api.get_id_by_name(browser_id),
                product_id=None,
                is_pre=is_pre,
                log=None
            )
            
            # 3) 发送完成 => 删除视频文件
            if os.path.exists(video_path):
                os.remove(video_path)
                logger.info(f"已删除 {video_path}")
        
        # 4) 全部发送完成 => 删除文本文件
        for item in to_send_list:
            txt_path = item["txt_path"]
            if os.path.exists(txt_path):
                os.remove(txt_path)
                logger.info(f"已删除 {txt_path}")
        
        self.switch_clash_mode("Rule")
        self.switch_clash_profile("root")
        
        logger.info("🎉🎉🎉待发送视频,全部发布完成!")

    def switch_clash_mode(self, mode_value):
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

    def switch_clash_profile(self, config_name):
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
            ensure_clash_config_fields(config_path, self.required_fields)
        else:
            ensure_clash_config_fields(config_path, self.required_fields2)

        try:
            url = f"{clash_api_url}/configs?force=true"
            data = {"path": config_path}

            resp = requests.put(url, headers=headers, json=data, timeout=5)
            if resp.status_code == 204:
                logger.info(f"成功将 Clash 整体切换为配置 {config_name}")
            else:
                logger.error(f"切换配置失败: {resp.status_code}, resp={resp.text}")
        except Exception as e:
            logger.error(f"切换配置时异常: {e}")
    
    def switch_clash_global(self):
        """
        mode_value: "Rule", "Global", "direct"...
        """
        clash_api_url = "http://127.0.0.1:9090"
        clash_token   = "517DE8FBC646FEAD84A5CC1432A578F2"
        headers = {"Authorization": f"Bearer {clash_token}"}

        try:
            url = f"{clash_api_url}/proxies/GLOBAL"
            data = {"name": "♻️ 自动选择"}
            r = requests.put(url, headers=headers, json=data, timeout=5)
            if r.status_code == 204:
                logger.info(f"成功切换GLOBAL为 ♻️ 自动选择")
            else:
                logger.error(f"切换GLOBAL失败: code={r.status_code}, resp={r.text}")
        except Exception as e:
            logger.error(f"切换GLOBAL异常: {e}")

    def get_video_duration(self, video_path):
        """使用 mutagen 获取视频的时长，返回时长（秒）"""
        try:
            video = MP4(video_path)
            duration = video.info.length  # 获取视频的时长（以秒为单位）
            print(f"视频时长：{duration}秒")
            return duration
        except Exception as e:
            logger.error(f"获取视频时长时发生错误: {e}")
            return 0

    def cut_video(self, input_file, output_file, start_time, duration, video_title, part_label=None):
        """
        使用 ffmpeg 截取视频，并重新编码:
        1) 从 start_time 开始, 截取 duration 秒
        2) scale 到宽=1080, 若高度 >1920 则等比缩小, 否则 pad 黑色 => 9:16 (1080x1920)
        3) 顶部(1/4处)多行文字(来自 video_title)，使用 (w-text_w)/2 水平居中
        4) 若 part_label 有值，则在底部(最后200px附近)再绘一行白字(不加白底)
        5) 去掉原视频 metadata
        """
        try:
            # 简单多行拆分: 每行最多 max_chars_per_line 个字符
            def wrap_text(text, max_chars_per_line=35):
                lines = []
                for i in range(0, len(text), max_chars_per_line):
                    lines.append(text[i : i + max_chars_per_line])
                return "\n".join(lines)

            wrapped_title = wrap_text(video_title, max_chars_per_line=35)

            # 根据平台替换成有效字体:
            # Windows: font_path = "C:/Windows/Fonts/Arial.ttf"
            # macOS:   font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
            # Linux:   font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"

            # A) 强制竖屏(1080x1920)
            filters = [
                "scale=1080:-1:force_original_aspect_ratio=decrease",
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
            ]

            # B) 顶部多行文本 => 多行都水平居中
            #   做法: x=(w-text_w)/2, y=(h/4 - text_h/2)
            #   fix_bounds=1 避免文字越界被截
            draw_top = (
                f"drawtext=fontfile='{font_path}':"
                f"text='{wrapped_title}':"
                "fontcolor=white:fontsize=64:line_spacing=10:fix_bounds=1:"
                "x=(w-text_w)/2:y=(h/5 - text_h/2):"
                "shadowcolor=black:shadowx=2:shadowy=2"
            )
            filters.append(draw_top)

            # C) 若 part_label => 在底部显示一行白字
            if part_label:
                # 假设放在 y= (1920 - 100 - text_h/2) 附近
                # 或者用 y= 1720 + (200-text_h)/2 也可以
                # 这里示例写 y=(h-100 - text_h/2)
                draw_bottom = (
                    f"drawtext=fontfile='{font_path}':"
                    f"text='{part_label}':"
                    "fontcolor=#434343:fontsize=200:line_spacing=10:fix_bounds=1:"
                    "x=(w-text_w)/2:y=(h-400 - text_h/2):"
                    "shadowcolor=black:shadowx=2:shadowy=2"
                )
                filters.append(draw_bottom)

            vf_filter = ",".join(filters)

            command = [
                get_ffmpeg_path(),
                '-i', input_file,
                '-nostdin',
                '-ss', str(start_time),
                '-t', str(duration),
                '-vf', vf_filter,

                '-c:v', 'libx264',
                '-crf', '18',
                '-preset', 'fast',

                '-c:a', 'aac',
                '-b:a', '128k',

                '-map_metadata', '-1',
                '-y',
                output_file
            ]

            subprocess.run(command, check=True)
            logger.info(f"视频切割/缩放/加文字完成: {output_file}")

        except Exception as e:
            logger.error(f"cut_video时发生错误: {e}")