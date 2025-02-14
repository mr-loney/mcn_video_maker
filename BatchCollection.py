import wx
import os
import threading
import time
import random
import string
import requests
import message_dialog
import re
import wx.lib.scrolledpanel as scrolled
import concurrent.futures
import shutil
import subprocess
import sys
import platform

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

class BatchCollectionFrame(wx.Frame):
    def __init__(self, parent, parent_folder, subfolders_list):
        super().__init__(parent, title="资源采集/预处理", size=(1000, 800))

        self.hhm_api = 'https://h.aaaapp.cn/single_post'
        self.user_id = 'C81E028D9DC2F636F06CA19862C'
        self.secret_key = 'eac9387cb705c2dd70cd07e216c'

        self.parent = parent
        self.parent_folder = parent_folder
        
        # 扫描子文件夹
        # self.subfolders_list = []
        # self.scan_subfolders_without_runjson()
        self.subfolders_list = subfolders_list

        # 主面板
        panel = wx.Panel(self)
        main_vbox = wx.BoxSizer(wx.VERTICAL)

        # 顶部提示
        lbl_info = wx.StaticText(panel, label="为每个子文件夹粘贴其需要下载的 URL（多行） - [p_1]前缀,代表批量拉取个人主页第一页")
        main_vbox.Add(lbl_info, 0, wx.LEFT | wx.TOP, 10)

        # 使用一个 ScrolledPanel，便于在子文件夹过多时滚动
        self.scrolled_panel = scrolled.ScrolledPanel(panel, style=wx.VSCROLL)
        self.scrolled_panel.SetAutoLayout(1)
        self.scrolled_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        
        # 让 scrolled_panel 有一个 vbox 来装各子文件夹的 UI
        self.vbox_folders = wx.BoxSizer(wx.VERTICAL)
        self.folder_input_controls = []  # [(folder_name, text_ctrl), ...]

        for folder in self.subfolders_list:
            # 文件夹名
            folder_label = wx.StaticText(self.scrolled_panel, label=f"文件夹：{folder}")
            self.vbox_folders.Add(folder_label, 0, wx.TOP | wx.LEFT, 5)

            # 多行输入框
            # 使用自定义 PassThroughTextCtrl
            text_ctrl = PassThroughTextCtrl(
                self.scrolled_panel,
                style=wx.TE_MULTILINE | wx.TE_NO_VSCROLL,  # 去掉 wx.VSCROLL
                size=(-1, 60)
            )
            # text_ctrl = wx.TextCtrl(self.scrolled_panel, style=wx.TE_MULTILINE | wx.VSCROLL, size=(-1, 60))
            self.vbox_folders.Add(text_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

            # 打开文件夹按钮
            btn_open_folder = wx.Button(self.scrolled_panel, label="打开文件夹")
            btn_open_folder.Bind(wx.EVT_BUTTON, lambda event, folder=folder: self.on_open_folder_click(event, folder))
            self.vbox_folders.Add(btn_open_folder, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

            # 记录
            self.folder_input_controls.append((folder, text_ctrl))

            # 加一条分隔线
            line = wx.StaticLine(self.scrolled_panel)
            self.vbox_folders.Add(line, 0, wx.EXPAND | wx.ALL, 5)

        self.scrolled_panel.SetSizer(self.vbox_folders)
        
        # 将 scrolled_panel 放入 main_vbox
        main_vbox.Add(self.scrolled_panel, 1, wx.EXPAND | wx.ALL, 5)

        # 底部按钮
        btn_hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_collect = wx.Button(panel, label="采集")
        self.btn_collect.Bind(wx.EVT_BUTTON, self.on_collect_click)
        btn_hbox.Add(self.btn_collect, 0, wx.RIGHT, 10)

        self.btn_extract_frames_audio = wx.Button(panel, label="抽帧及音频提取")
        self.btn_extract_frames_audio.Bind(wx.EVT_BUTTON, self.on_extract_frames_audio_click)
        btn_hbox.Add(self.btn_extract_frames_audio, 0, wx.RIGHT, 10)

        self.btn_cancel = wx.Button(panel, label="取消")
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.on_cancel_click)
        btn_hbox.Add(self.btn_cancel, 0, wx.RIGHT, 10)

        # loading 提示
        self.loading_text = wx.StaticText(panel, label="")
        btn_hbox.AddStretchSpacer()
        btn_hbox.Add(self.loading_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        main_vbox.Add(btn_hbox, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 5)

        panel.SetSizer(main_vbox)
    
    def on_open_folder_click(self, event, folder):
        """
        打开指定文件夹
        """
        folder_path = os.path.join(self.parent_folder, folder)
        if os.path.exists(folder_path):
            # 使用系统默认文件浏览器打开文件夹
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder_path])
            else:
                subprocess.run(["xdg-open", folder_path])
        else:
            wx.MessageBox(f"文件夹不存在: {folder_path}", "错误", wx.OK | wx.ICON_ERROR)

    def on_extract_frames_audio_click(self, event):
        # 显示 loading
        self.loading_text.SetLabel("正在抽帧及提取音乐，请稍候...")
        self.loading_text.Update()

        def process():
            tasks = []

            # 遍历子文件夹，寻找有 reslib 的子文件夹
            for subfolder in self.subfolders_list:
                reslib_path = os.path.join(self.parent_folder, subfolder, "reslib")
                if os.path.exists(reslib_path):
                    tasks.append(reslib_path)

            if not tasks:
                wx.CallAfter(message_dialog.show_custom_message_dialog, self, "没有找到含有 reslib 的子文件夹！", "提示")
                return

            def process_folder(folder_path):
                # 遍历 reslib 下的所有子文件夹
                subfolders = [
                    os.path.join(folder_path, subfolder)
                    for subfolder in os.listdir(folder_path)
                    if os.path.isdir(os.path.join(folder_path, subfolder))
                ]

                for subfolder in subfolders:
                    mp4_files = [
                        os.path.join(subfolder, f)
                        for f in os.listdir(subfolder)
                        if f.endswith(".mp4")
                    ]
                    if not mp4_files:
                        print(f"未找到视频文件，跳过: {subfolder}")
                        continue

                    # 抽帧
                    frames_folder = os.path.join(subfolder, "frames")
                    if os.path.exists(frames_folder):
                        shutil.rmtree(frames_folder)  # 删除已有 frames 文件夹
                    os.makedirs(frames_folder, exist_ok=True)

                    for mp4_file in mp4_files:
                        self.extract_frames_with_ffmpeg(mp4_file, frames_folder)

                    # 提取音频
                    for mp4_file in mp4_files:
                        audio_path = os.path.splitext(mp4_file)[0] + ".wav"
                        self.extract_audio_with_ffmpeg(mp4_file, audio_path)

                    # 将音频文件拷贝到根文件夹
                    root_audio_path = os.path.join(os.path.dirname(folder_path), "audio.wav")
                    if not os.path.exists(root_audio_path):
                        shutil.copy(audio_path, root_audio_path)

            # 多线程执行
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(process_folder, folder) for folder in tasks]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"处理失败: {e}")
            
            wx.CallAfter(self.loading_text.SetLabel, "")
            wx.CallAfter(message_dialog.show_custom_message_dialog, self, "抽帧及音频提取完成！🎉", "提示")
        
        # 在子线程中运行处理逻辑
        threading.Thread(target=process).start()

    def extract_frames_with_ffmpeg(self, video_path, output_folder, interval=3):
        """
        使用 ffmpeg 抽帧，确保提取第一帧和最后一帧，命名为 start.png 和 end.png，其余每 interval 秒抽一帧。
        """
        try:
            # 确保输出文件夹存在
            os.makedirs(output_folder, exist_ok=True)

            # 提取第一帧并命名为 start.png
            start_frame_path = os.path.join(output_folder, "00000.png")
            start_command = [
                get_ffmpeg_path(), "-i", video_path, "-vf", "select=eq(n\\,0)", "-vsync", "vfr",
                start_frame_path, "-hide_banner", "-loglevel", "error"
            ]

            print(f"正在提取第一帧: {video_path}")
            subprocess.run(start_command, check=True)
            print(f"完成提取第一帧: {start_frame_path}")

            # 提取最后一帧并命名为 end.png
            end_frame_path = os.path.join(output_folder, "end.png")
            end_command = [
                get_ffmpeg_path(), "-sseof", "-1", "-i", video_path, "-update", "1", "-q:v", "2",
                end_frame_path, "-hide_banner", "-loglevel", "error"
            ]
            print(f"正在提取最后一帧: {video_path}")
            subprocess.run(end_command, check=True)
            print(f"完成提取最后一帧: {end_frame_path}")

            # 提取每 interval 秒的帧
            output_pattern = os.path.join(output_folder, "%05d.png")
            interval_command = [
                get_ffmpeg_path(), "-i", video_path, "-vf",
                f"fps=1/{interval}", output_pattern, "-hide_banner", "-loglevel", "error"
            ]
            print(f"正在每 {interval} 秒抽帧: {video_path}")
            subprocess.run(interval_command, check=True)
            print(f"完成抽帧: {video_path}")

        except subprocess.CalledProcessError as e:
            print(f"抽帧失败: {video_path}, 错误: {e}")

    def extract_audio_with_ffmpeg(self, video_path, output_path):
        """使用 ffmpeg 提取音频"""
        try:
            command = [
                get_ffmpeg_path(), "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100",
                "-ac", "2", output_path, "-hide_banner", "-loglevel", "error"
            ]
            print(f"正在提取音频: {video_path}")
            subprocess.run(command, check=True)
            print(f"完成音频提取: {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"音频提取失败: {video_path}, 错误: {e}")

    def scan_subfolders_without_runjson(self):
        """扫描 self.parent_folder 下所有子文件夹，如果没有 run.json 则加入 subfolders_list，并按创建时间排序"""
        if not os.path.isdir(self.parent_folder):
            return

        folder_with_time = []  # 存储子文件夹路径和创建时间的元组

        # for item in os.listdir(self.parent_folder):
        #     item_path = os.path.join(self.parent_folder, item)
        #     if os.path.isdir(item_path):
        #         runjson_path = os.path.join(item_path, "close.json")
        #         if not os.path.exists(runjson_path):
        #             folder_with_time.append(item)
        
        # self.subfolders_list = folder_with_time

        for item in os.listdir(self.parent_folder):
            item_path = os.path.join(self.parent_folder, item)
            if os.path.isdir(item_path):
                runjson_path = os.path.join(item_path, "close.json")
                if not os.path.exists(runjson_path):
                    # 获取创建时间
                    creation_time = os.path.getctime(item_path)
                    folder_with_time.append((item, creation_time))

        # 按创建时间排序（从旧到新）
        folder_with_time.sort(key=lambda x: x[1])

        # 提取排序后的文件夹名称
        self.subfolders_list = [folder for folder, _ in folder_with_time]

    def on_collect_click(self, event):
        """点击“采集”按钮"""
        if not self.folder_input_controls:
            wx.MessageBox("没有需要采集的子文件夹！", "提示", wx.OK | wx.ICON_WARNING)
            return

        # 逐个文件夹获取多行URL
        tasks = []
        for folder_name, ctrl in self.folder_input_controls:
            urls_text = ctrl.GetValue().strip()
            if not urls_text:
                # 如果为空，这个文件夹就不下载
                continue

            url_list = [line.strip() for line in urls_text.splitlines() if line.strip()]
            if url_list:
                tasks.append((folder_name, url_list))

        if not tasks:
            wx.CallAfter(message_dialog.show_custom_message_dialog, self, "没有有效的 URL！", "提示")
            return

        # 显示 loading
        self.loading_text.SetLabel("正在采集，请稍候...")
        self.loading_text.Update()

        # 可以使用多线程
        def worker(folder_name, urls):
            """示例工作函数：下载到 folder_name/reslib"""
            for url in urls:
                try:
                    # 判断是否为个人主页模式 (posts_n)
                    match = re.match(r"\[p_(\d+)\]", url)
                    if match:
                        # 解析个人主页模式
                        n = int(match.group(1))  # 提取 n 的值
                        base_url = url.replace(match.group(0), "").strip()  # 去掉 (p_n)，获取基础 URL
                        complete_url_list = self.fetch_personal_homepage_urls(base_url, n)
                    else:
                        # 普通模式
                        complete_url_list = self.res_find_url(url)
                    
                    # 遍历完整的 URL 列表进行下载
                    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                        def download_task(real_url, title, mtype):
                            """单个下载任务"""
                            try:
                                random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
                                if title == "":
                                    target_folder = os.path.join(self.parent_folder, folder_name, "reslib", random_suffix)
                                else:
                                    target_folder = os.path.join(
                                        self.parent_folder, folder_name, "reslib", clean_and_trim_title(title) + "_" + random_suffix
                                    )
                                os.makedirs(target_folder, exist_ok=True)
                                self.res_download(real_url, target_folder, mtype)
                            except Exception as e:
                                print(f"下载失败: {real_url}, 错误: {e}")

                        # 提交下载任务到线程池
                        futures = [executor.submit(download_task, real_url, title, mtype) for real_url, title, mtype in complete_url_list]

                        # 等待所有任务完成
                        for future in concurrent.futures.as_completed(futures):
                            try:
                                future.result()  # 获取任务结果，确保完成
                            except Exception as e:
                                print(f"下载任务出错: {e}")
                except Exception as e:
                    print(f"[{folder_name}] 下载失败: {url}, 错误: {e}")

        def clean_and_trim_title(title, max_length=40):
            # 去掉反斜杠、斜杠和换行符
            cleaned_title = title.replace("\\", "").replace("/", "").replace("\n", "")
            # 截取前 max_length 个字符
            trimmed_title = cleaned_title[:max_length]
            return trimmed_title

        # 简单地用3个线程并行处理 tasks
        # 如果 tasks 数量很多，需要再做更灵活的调度
        self.threads = []
        for i, (folder, url_list) in enumerate(tasks):
            t = threading.Thread(target=worker, args=(folder, url_list))
            t.start()
            self.threads.append(t)
            if i == 2:  # 只示范启动3个线程
                break

        # 启动一个定时器，轮询检查是否下载完成
        self.check_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_check_threads, self.check_timer)
        self.check_timer.Start(500)  # 0.5秒检查一次

    def on_check_threads(self, event):
        """检查线程是否结束"""
        alive = any(t.is_alive() for t in self.threads)
        if not alive:
            self.check_timer.Stop()
            self.loading_text.SetLabel("")
            wx.CallAfter(message_dialog.show_custom_message_dialog, self, "资源采集完成！", "提示")

    def on_cancel_click(self, event):
        """点击“取消”按钮"""
        self.Close()

    # -----------------------------------------------------------------------------
    # 以下为示例方法，需要你实际实现或替换成自己已有逻辑
    # -----------------------------------------------------------------------------
    def res_find_url(self, url):
        print("开始解析资源url: " + url)
        params = {
            'userId': '8C1C697A1D9D3E1A891E88F5DB64F2B6',
            'secretKey': '994a4ade05d06bd5aaa105d839bbbc28',
            'url': url
        }
        r = requests.post(self.hhm_api, json=params, verify=False).json()
        res_arr = []
        
        if r["code"] == 200:
            for index, mdata in enumerate(r["data"]["medias"]):
                # 多图
                if mdata["media_type"] == "image":
                    res_arr.append((mdata["resource_url"], str(index) + "_" + r["data"]["text"], "image"))
                    print("资源url解析成功")
                # 视频
                if mdata["media_type"] == "video":
                    res_arr.append((mdata["resource_url"], str(index) + "_" + r["data"]["text"], "video"))
                    # if "formats" in mdata:
                    #     res_arr.append((mdata["formats"][0]["video_url"], str(index) + "_" + r["data"]["text"], "video"))
                    # else:
                    #     res_arr.append((mdata["resource_url"], str(index) + "_" + r["data"]["text"], "video"))
                    print("资源url解析成功")
            return res_arr
        else:
            print("资源url解析失败")
            return res_arr

    def fetch_personal_homepage_urls(self, base_url, n):
            """
            拉取个人主页模式的资源 URL 列表
            :param base_url: 个人主页基础 URL
            :param n: 索引范围 (0 到 n)
            :return: [(resource_url, text), ...] 格式的 URL 列表
            """
            new_url_list = []
            cursor = ""
            for index in range(n):
                print(f"开始解析个人主页资源，第 {index + 1} 页: {base_url}")
                if not cursor == "error":
                    cursor = self.find_urls(new_url_list, base_url, cursor)
            return new_url_list
    
    def find_urls(self, new_url_list, base_url, cursor):
        params = {}
        if cursor == "":
            params = {
                'userId': '8C1C697A1D9D3E1A891E88F5DB64F2B6',
                'secretKey': '994a4ade05d06bd5aaa105d839bbbc28',
                'url': base_url
            }
        else:
            params = {
                'userId': '8C1C697A1D9D3E1A891E88F5DB64F2B6',
                'secretKey': '994a4ade05d06bd5aaa105d839bbbc28',
                'url': base_url,
                'cursor': cursor
            }
        
        try:
            r = requests.post("https://h.aaaapp.cn/posts", json=params, verify=False).json()
            if r["code"] == 200:
                data_list = r["data"]['posts']
                for i, item in enumerate(data_list):
                    for index, mdata in enumerate(item["medias"]):
                        # 多图
                        if mdata["media_type"] == "image":
                            new_url_list.append((mdata["resource_url"], str(i) + "_" + str(index) + "_" + item["text"], "image"))
                            print("资源url解析成功")
                        # 视频
                        if mdata["media_type"] == "video":
                            new_url_list.append((mdata["resource_url"], str(i) + "_" + str(index) + "_" + item["text"], "video"))
                            # if "formats" in mdata:
                            #     new_url_list.append((mdata["formats"][0]["video_url"], str(i) + "_" + str(index) + "_" + item["text"], "video"))
                            # else:
                            #     new_url_list.append((mdata["resource_url"], str(i) + "_" + str(index) + "_" + item["text"], "video"))
                            print("资源url解析成功")
                print(f"个人主页解析成功1次，共 {len(data_list)} 条资源")
                return r["data"]['next_cursor']
            else:
                print(f"个人主页解析失败1次，错误代码: {r['code']}")
                return "error"

        except Exception as e:
            print(f"个人主页解析失败1次，错误: {e}")
            return "error"
    
    def res_download(self, real_url, target_folder, mtype):
        """
        下载真实文件到 target_folder
        """
        if real_url == "":
            print(f"下载失败: {real_url} 为空")
            return
        
        try:
            # 确保目标文件夹存在
            os.makedirs(target_folder, exist_ok=True)
            
            # 获取文件名
            if mtype == "video":
                filename = "res.mp4"
            else:
                filename = "res.jpg"
            file_path = os.path.join(target_folder, filename)
            
            # 设置模拟的请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.63 Safari/537.36",
                "Referer": real_url,  # 一些服务器要求Referer
            }
            
            # 开始下载
            print(f"正在下载: {real_url}")
            with requests.get(real_url, headers=headers, stream=True, timeout=30) as response:
                response.raise_for_status()  # 如果状态码不是 200，会抛出异常
                with open(file_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):  # 每次读取 8 KB
                        file.write(chunk)
            
            print(f"下载完成: {filename} => {target_folder}")
        except requests.exceptions.RequestException as e:
            print(f"下载失败: {real_url}, 错误: {e}")
        except Exception as e:
            print(f"文件保存失败: {real_url}, 错误: {e}")

class PassThroughTextCtrl(wx.TextCtrl):
    """
    当文本内容不足以让 TextCtrl 出现滚动条时，滚轮事件传给父级(ScrolledPanel)；
    当文本内容超过可见区域，TextCtrl 自己处理滚轮。
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.Bind(wx.EVT_MOUSEWHEEL, self.on_mousewheel)

    def on_mousewheel(self, event):
        # 计算当前可见行数 vs 总行数
        line_count = self.GetNumberOfLines()
        if line_count <= 0:
            # 空文本，直接把事件交给上级去滚
            self.GetParent().GetEventHandler().ProcessEvent(event)
            return

        # 每行高度
        line_height = self.GetCharHeight()
        # 可见区域能容纳多少行
        visible_lines = self.GetClientSize().height // line_height
        # 当前滚动位置
        pos_y = self.GetScrollPos(wx.VERTICAL)
        # 最大滚动范围
        max_y = self.GetScrollRange(wx.VERTICAL) - visible_lines

        # 判断是否还有可滚动空间
        can_scroll_up = (pos_y > 0 and event.GetWheelRotation() > 0)
        can_scroll_down = (pos_y < max_y and event.GetWheelRotation() < 0)
        can_scroll_in_textctrl = can_scroll_up or can_scroll_down

        if can_scroll_in_textctrl:
            # TextCtrl 自己可以滚
            event.Skip()  # 交给 TextCtrl 默认逻辑
        else:
            # TextCtrl 滚完了 或 还没出现滚动条，则把滚动交给 ScrolledPanel
            self.GetParent().GetEventHandler().ProcessEvent(event)