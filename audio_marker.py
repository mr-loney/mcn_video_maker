# audio_marker_wx.py
import wx
import wx.lib.scrolledpanel as scrolled
from wx.lib.scrolledpanel import ScrolledPanel
import wave
import os
import time
import numpy as np
import simpleaudio as sa
import requests
import translate
import shutil
import random
import string
import re

import matplotlib
matplotlib.use("WXAgg")
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure

from pydub import AudioSegment
from scene_dialog import SceneSelectionDialog
import message_dialog

MARKER_MONTAGE_TYPE = None
MARKER_AUDIO_PATH = None
SCENE_CHOICES = []
MARKER_LANGUAGE = "en-US"

def open_mcn_audio_window(audio_path, montage_type, pre_window):
    """
    与原 Tkinter 版对应的接口，用于在主窗口中调用。
    但在 wxPython 版，我们直接在 on_asr_done() 中 new 一个 AudioMarkerFrame 即可，
    这个函数可自定义是否需要。
    """
    pass

def is_wav_file(file_path):
    try:
        with wave.open(file_path, "rb") as wf:
            return True
    except wave.Error:
        return False

def convert_to_wav(file_path):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(base_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    original_filename = os.path.basename(file_path).rsplit(".", 1)[0]
    wav_path = os.path.join(cache_dir, f"{original_filename}_converted.wav")

    audio = AudioSegment.from_file(file_path)
    audio.export(wav_path, format="wav")
    print(f"转换完成，WAV 文件保存到: {wav_path}")
    return wav_path

class AudioMarkerFrame(wx.Frame):
    def __init__(self, parent, audio_path, montage_type, language, main_window):
        super().__init__(parent, title="MCN模版打点", size=(800, 500))

        global MARKER_MONTAGE_TYPE, MARKER_AUDIO_PATH, MARKER_LANGUAGE
        MARKER_MONTAGE_TYPE = montage_type
        MARKER_AUDIO_PATH = audio_path
        MARKER_LANGUAGE = language

        self.main_window = main_window  # 用于关闭当前窗口后返回主窗口

        # 面板
        panel = wx.Panel(self)
        panel.SetBackgroundColour("#444444")

        # 垂直布局
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 波形图所在的 Panel
        self.fig = Figure(figsize=(6, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)

        # 新增：鼠标是否按下
        self.mouse_down = False

        self.canvas = FigureCanvas(panel, -1, self.fig)
        self.canvas.mpl_connect("button_press_event", self.on_mouse_down)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_up)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)  # 如果要处理拖拽结束

        # 初始化波形数据
        self.is_playing = False
        self.play_obj = None
        self.wave_data = None
        self.sample_rate = None
        self.current_frame = 0
        self.total_frames = 1
        self.update_interval_ms = 50
        self.play_start_time = 0

        # 段落点相关
        self.paragraph_timestamps = []
        self.paragraph_lines = []
        self.mouse_in_wave = False
        self.mouse_x = None

        # 加载音频
        self.load_audio(audio_path)
        self.draw_waveform()

        # 按钮栏：播放/暂停
        hbox_controls = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_play = wx.Button(panel, label="播放")
        self.btn_play.Bind(wx.EVT_BUTTON, self.toggle_play)
        hbox_controls.Add(self.btn_play, 0, wx.RIGHT, 20)

        self.lbl_info = wx.StaticText(panel, label="暂停中")
        self.lbl_info.SetForegroundColour(wx.Colour("red"))
        hbox_controls.Add(self.lbl_info, 0, wx.ALIGN_CENTER_VERTICAL)

        # 自动分段下拉框
        hbox_controls.AddStretchSpacer()
        auto_segment_label = wx.StaticText(panel, label="自动分段：")
        hbox_controls.Add(auto_segment_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.segment_choices = ["0", "2", "3", "4", "5", "6", "7", "8", "9", "10"]  # 自动分段选项
        self.segment_combo = wx.Choice(panel, choices=self.segment_choices)
        self.segment_combo.SetSelection(0)  # 默认选中"0"
        self.segment_combo.Bind(wx.EVT_CHOICE, self.on_segment_change)  # 绑定事件
        hbox_controls.Add(self.segment_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        
        # 显示翻译按钮
        self.btn_asr = wx.Button(panel, label="显示翻译")
        self.btn_asr.Bind(wx.EVT_BUTTON, self.on_asr_button_click)
        hbox_controls.Add(self.btn_asr, 0, wx.RIGHT, 10)

        # 添加 "创建模版" 按钮
        self.btn_create_template = wx.Button(panel, label="创建模版")
        self.btn_create_template.Bind(wx.EVT_BUTTON, self.create_template)
        hbox_controls.Add(self.btn_create_template, 0, wx.RIGHT, 10)

        # 提示标签
        tips_label = wx.StaticText(panel, label="A:加播放段落|S:加光标段落|D:撤销段落")
        tips_label.SetForegroundColour("#999999")
        hbox_controls.AddStretchSpacer()

        # 再添加 tips_label，且只使用垂直方向对齐和一些右边距
        hbox_controls.Add(tips_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 黑色半透明蒙层
        self.loading_overlay = wx.Panel(panel, size=self.GetClientSize())
        self.loading_overlay.SetBackgroundColour(wx.Colour(0, 0, 0, 28))  # 黑色，半透明
        self.loading_overlay.Hide()

        # 红色 Loading 提示
        self.loading_label = wx.StaticText(
            self.loading_overlay,
            label="",
            style=wx.ALIGN_CENTER
        )
        self.loading_label.SetForegroundColour(wx.Colour("red"))
        font = self.loading_label.GetFont()
        font.PointSize += 10  # 增大字体
        self.loading_label.SetFont(font)
        
        vbox.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(hbox_controls, 0, wx.EXPAND | wx.ALL, 5)

        # 1) 字幕显示控件
        self.lbl_subtitle = wx.StaticText(panel, label="", style=wx.ALIGN_CENTER)
        self.lbl_subtitle.SetForegroundColour(wx.Colour("yellow"))
        font_subtitle = self.lbl_subtitle.GetFont()
        font_subtitle.PointSize += 3
        self.lbl_subtitle.SetFont(font_subtitle)

        # 将字幕控件放到最下方
        vbox.Add(self.lbl_subtitle, 0, wx.EXPAND | wx.ALL, 5)
        # vbox.Add(self.lbl_subtitle, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 5)

        panel.SetSizer(vbox)
        
        # 绑定键盘事件
        self.canvas.Bind(wx.EVT_KEY_DOWN, self.on_key_pressed)
        # 让 canvas 能够接收到键盘焦点
        self.canvas.SetFocus()

        # 定时器来刷新播放进度
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_cursor, self.timer)
        self.timer.Start(self.update_interval_ms)

        # 绑定窗口关闭事件
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # self.Centre()
        self.CentreOnParent()
        self.start_play()
    
    def clean_folder(self, folder_path):
        """
        清理指定文件夹：
        1. 删除除名为 "output" 和 "reslib" 以外的文件夹。
        2. 删除除音频文件和 "run.json" 文件以外的其他文件。
        
        :param folder_path: 要清理的文件夹路径
        """
        # 检查文件夹是否存在
        if not os.path.exists(folder_path):
            print(f"文件夹 {folder_path} 不存在！")
            return

        # 定义保留的文件夹名称
        reserved_folders = {"output", "reslib"}
        # 定义保留的文件名称
        reserved_files = {"run.json"}
        # 定义音频文件扩展名
        audio_extensions = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"}

        # 遍历文件夹中的内容
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)

            if os.path.isdir(item_path):
                # 如果是文件夹且不在保留列表中，删除
                if item not in reserved_folders:
                    print(f"删除文件夹: {item_path}")
                    shutil.rmtree(item_path)  # 删除整个文件夹
            elif os.path.isfile(item_path):
                # 如果是文件且不属于音频文件和 "run.json"，删除
                _, ext = os.path.splitext(item)
                if item not in reserved_files and ext.lower() not in audio_extensions:
                    print(f"删除文件: {item_path}")
                    os.remove(item_path)  # 删除文件
    
    def generate_unique_filename(self, folder_name):
        """
        生成唯一文件名：
        使用当前时间的明文格式和随机数生成一个新的唯一文件名。
        
        :return: 生成的唯一文件名（不带扩展名）
        """
        # 获取当前时间并格式化为明文格式
        timestamp = time.strftime("%Y_%m_%d_%H_%M_%S")  # 格式为 2025_01_20_12_07_48

        # 生成随机字符串（6位）
        random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

        # 组合文件名
        unique_filename = f"{timestamp}_{folder_name}_{random_str}"
        return unique_filename

    def create_template(self, event):
        """
        根据段落时间戳创建文件夹模版，并保存每段字幕到对应文件夹。
        同时在 MARKER_AUDIO_PATH 的同级目录下生成 config.json 文件。
        """
        if not MARKER_AUDIO_PATH:
            print("音频路径未设置，无法创建模版。")
            return
        # 获取 MARKER_AUDIO_PATH 的上一级文件夹名称
        parent_folder = os.path.basename(os.path.dirname(MARKER_AUDIO_PATH))
         # 获取 MARKER_AUDIO_PATH 的上上一级文件夹名称
        grandparent_dir = os.path.basename(os.path.dirname(os.path.dirname(MARKER_AUDIO_PATH)))

        unique_filename = self.generate_unique_filename(parent_folder)
        ftp_path = f"ftp://183.6.90.205:2221/mnt/NAS/mcn/aigclib/{unique_filename}"

        # 获取音频文件名
        audio_filename = os.path.basename(MARKER_AUDIO_PATH)
        audio_relative_path = f"{ftp_path}/{{userid}}/{audio_filename}"
        
        # 使用正则表达式提取符合 [xxxxx]_adsadsada 格式的 xxxxx
        match = re.search(r"\[([^\]]+)\]", parent_folder)
        parent_match = re.search(r"\[([^\]]+)\]", grandparent_dir)

        # 确保时间戳是排序的
        sorted_timestamps = sorted(self.paragraph_timestamps)

        # 直接使用 self.total_frames 和 self.sample_rate 计算音频总时长
        try:
            total_duration = self.total_frames / self.sample_rate  # 总时长（秒）
            print(f"音频总时长: {total_duration} 秒")
        except ZeroDivisionError:
            print("采样率为 0，无法计算总时长")
            total_duration = 0  # 如果采样率为 0，设置为 0
        
        # 计算每段的持续时间
        durations = [(sorted_timestamps[i] - sorted_timestamps[i - 1]) / 1000.0 if i > 0 else sorted_timestamps[0] / 1000.0 for i in range(len(sorted_timestamps))]
        if len(sorted_timestamps) == 0:
            durations.append(total_duration)  # 最后一段持续时间为总时长减去最后一个时间戳
        else:
            durations.append(max(0, total_duration - sorted_timestamps[-1] / 1000.0))  # 最后一段持续时间为总时长减去最后一个时间戳

        # 获取音频所在目录
        audio_dir = os.path.dirname(MARKER_AUDIO_PATH)
        if not os.path.exists(audio_dir):
            print(f"音频目录不存在: {audio_dir}")
            return

        if parent_match:
            extracted_value = parent_match.group(1)
            use_anonymous = False
            social_account = extracted_value
            matrix_template = extracted_value + "的矩阵模版"
        elif match:
            extracted_value = match.group(1)
            use_anonymous = False
            social_account = extracted_value
            matrix_template = extracted_value + "的矩阵模版"
        else:
            use_anonymous = True
            social_account = "ghost_0001"
            matrix_template = "ghost_0001的矩阵模版"

        # 初始化配置文件数据
        if MARKER_MONTAGE_TYPE == "多图模式":
            config_data = {
                "ftp_folder_name": unique_filename,
                "videos": [],
                "use_video_subtitle": f"{ftp_path}/{{userid}}/topmask/",
                "audio": audio_relative_path,
                "videos_asynconf": [],
                "use_anonymous": use_anonymous,
                "social_account": social_account,
                "matrix_template": matrix_template,
                "is_new_template": True,
                "tiktok_title": "Really wonderful!🎉🎉🎉",
                "tiktok_tags": "#foryou #fyp #tiktok #tiktokmademebuyit #viral #hot",
                "tiktok_at": "",
                "first_comment": "",
                "window_product": "",
                "music_name": "random",
                "music_index": "",
                "music_volume": 0.0,
                "original_volume": 1.0,
                "publish_time": "4:00,10:00,18:00",
                "repost_high_views": False,
                "repost_views_threshold": "",
                "is_create_human": False,
                "widget": "GenTemplateImage"
            }
        else:
            config_data = {
                "cmd": "splice_digital_human" if MARKER_MONTAGE_TYPE == "高级混剪" else "splice_digital_human",
                "ftp_folder_name": unique_filename,
                "videos": [],
                "use_video_subtitle": f"{ftp_path}/{{userid}}/topmask/",
                "audio": audio_relative_path,
                "videos_asynconf": [],
                "use_anonymous": use_anonymous,
                "social_account": social_account,
                "matrix_template": matrix_template,
                "is_new_template": True,
                "tiktok_title": "Really wonderful!",
                "tiktok_tags": "#foryou #fyp #tiktok #tiktokmademebuyit #viral #hot",
                "tiktok_at": "",
                "first_comment": "",
                "window_product": "",
                "music_name": "",
                "music_index": "",
                "music_volume": 0.0,
                "original_volume": 1.0,
                "publish_time": "4:00,10:00,18:00",
                "repost_high_views": False,
                "repost_views_threshold": "",
                "is_create_human": False,
                "widget": "GenVideo_Template2"
            }

        if MARKER_MONTAGE_TYPE == "高级混剪":
            # 获取段落数量
            num_scenes = len(sorted_timestamps) + 1  # 默认加第一幕

            # 弹窗选择场景类型
            global SCENE_CHOICES
            dialog = SceneSelectionDialog(self, num_scenes, SCENE_CHOICES)
            if dialog.ShowModal() == wx.ID_OK:
                SCENE_CHOICES = dialog.scene_choices
                print(f"场景选择已更新: {SCENE_CHOICES}")
                dialog.Destroy()
            else:
                dialog.Destroy()
                return
            
            # 生成数字人
            config_data["is_create_human"] = True
            
            # 清空存量文件
            self.clean_folder(os.path.dirname(MARKER_AUDIO_PATH))

            # 遍历每一幕，根据选择创建文件夹
            for i, choice in enumerate(SCENE_CHOICES):
                folder_name = str(i)
                folder_path = os.path.join(audio_dir, folder_name)

                try:
                    os.makedirs(folder_path, exist_ok=True)
                    print(f"成功创建文件夹: {folder_path}")

                    # 获取当前时间段的字幕
                    # if hasattr(self, 'asr_list') and self.asr_list:
                    #     start_time = 0 if i == 0 else sorted_timestamps[i - 1]
                    #     end_time = None if i == len(sorted_timestamps) else sorted_timestamps[i]

                        # lyrics = self.get_lyrics_in_time_range(start_time, end_time)
                        # lyric_path = os.path.join(folder_path, "lyric.txt")
                        # with open(lyric_path, "w", encoding="utf-8") as lyric_file:
                        #     lyric_file.write(lyrics)
                        # print(f"成功写入字幕: {lyric_path}")

                    # 判断场景类型，创建额外的文件夹
                    video2 = ""

                    video_asynconf = {}
                    digital_human_asynconf = {}
                    video2_asynconf = {}

                    if choice in [
                        "全屏内容",
                        "左上数字人头像+全屏内容",
                        "右上数字人头像+全屏内容",
                        "左下数字人头像+全屏内容",
                        "右下数字人头像+全屏内容",
                    ]:
                        content_folder = os.path.join(audio_dir, f"{folder_name}_content")
                        os.makedirs(content_folder, exist_ok=True)
                        print(f"成功创建内容文件夹: {content_folder}")

                        video = f"[cut_type:dir]{ftp_path}/{{userid}}/{folder_name}_content/"

                        video_asynconf = {"is_vertical":True, "cut_duration":5, "prompt":"Short video footage", "cut_count": 2}
                    elif choice == "全屏数字人+浮窗":
                        pop_folder = os.path.join(audio_dir, f"{folder_name}_pop")
                        os.makedirs(pop_folder, exist_ok=True)
                        print(f"成功创建浮窗文件夹: {pop_folder}")

                        video2 = f"[green_screen][cut_type:file]{ftp_path}/{{userid}}/{folder_name}_pop/"
                        video = ""

                        video2_asynconf = {"is_vertical":True, "cut_duration":5, "prompt":"Short video footage", "cut_count": 2}
                    elif choice == "全屏内容+浮窗":
                        content_folder = os.path.join(audio_dir, f"{folder_name}_content")
                        os.makedirs(content_folder, exist_ok=True)
                        print(f"成功创建内容文件夹: {content_folder}")

                        video = f"[cut_type:dir]{ftp_path}/{{userid}}/{folder_name}_content/"

                        pop_folder = os.path.join(audio_dir, f"{folder_name}_pop")

                        os.makedirs(pop_folder, exist_ok=True)
                        print(f"成功创建浮窗文件夹: {pop_folder}")

                        video2 = f"[green_screen][cut_type:file]{ftp_path}/{{userid}}/{folder_name}_pop/"

                        video_asynconf = {"is_vertical":True, "cut_duration":5, "prompt":"Short video footage", "cut_count": 2}
                        video2_asynconf = {"is_vertical":True, "cut_duration":5, "prompt":"Short video footage", "cut_count": 2}
                    else:
                        video = ""

                    # 根据选择设置 clip_style
                    clip_style = {
                        "全屏数字人": "only_human",
                        "全屏内容": "only_video",
                        "左上数字人头像+全屏内容": "video_below_human_tl",
                        "右上数字人头像+全屏内容": "video_below_human_tr",
                        "左下数字人头像+全屏内容": "video_below_human_bl",
                        "右下数字人头像+全屏内容": "video_below_human_br",
                        "全屏数字人+浮窗": "only_human",
                        "全屏内容+浮窗": "only_video"
                    }.get(choice, "only_video")

                    digital_human = f"[cut_type:dir]{ftp_path}/{{userid}}/{folder_name}/"
                    digital_human_asynconf = {"is_vertical":True, "cut_duration":5, "prompt":"Short video footage", "cut_count": 2}

                    config_data["videos"].append({
                        "video": video,
                        "digital_human": digital_human,
                        "duration": round(durations[i], 2),
                        "clip_style": clip_style,
                        "video2": video2
                    })

                    config_data["videos_asynconf"].append({
                        "video": video_asynconf,
                        "digital_human": digital_human_asynconf,
                        "video2": video2_asynconf,
                    })

                except Exception as e:
                    print(f"创建文件夹失败: {folder_path}，错误: {e}")
        elif MARKER_MONTAGE_TYPE == "多图模式":
            # 清空存量文件
            test = os.path.dirname(MARKER_AUDIO_PATH)
            self.clean_folder(os.path.dirname(MARKER_AUDIO_PATH))

            folder_names = [str(i) for i in range(len(sorted_timestamps) + 1)]  # 包含默认的"0"
            for i, folder_name in enumerate(folder_names):
                folder_path = os.path.join(audio_dir, folder_name)
                try:
                    os.makedirs(folder_path, exist_ok=True)
                    print(f"成功创建文件夹: {folder_path}")

                    # 获取当前时间段的字幕
                    # if hasattr(self, 'asr_list') and self.asr_list:
                    #     start_time = 0 if i == 0 else sorted_timestamps[i - 1]
                    #     end_time = None if i == len(sorted_timestamps) else sorted_timestamps[i]

                        # lyrics = self.get_lyrics_in_time_range(start_time, end_time)
                        # lyric_path = os.path.join(folder_path, "lyric.txt")
                        # with open(lyric_path, "w", encoding="utf-8") as lyric_file:
                        #     lyric_file.write(lyrics)
                        # print(f"成功写入字幕: {lyric_path}")

                    config_data["videos"].append(f"{ftp_path}/{{userid}}/{folder_name}/")
                    config_data["videos_asynconf"].append({"is_vertical":True, "cut_duration":5, "prompt":"Short video footage", "cut_count": 2})
                except Exception as e:
                    print(f"创建文件夹或写入字幕失败: {folder_path}，错误: {e}")
        else:  # 普通混剪
            # 清空存量文件
            test = os.path.dirname(MARKER_AUDIO_PATH)
            self.clean_folder(os.path.dirname(MARKER_AUDIO_PATH))

            folder_names = [str(i) for i in range(len(sorted_timestamps) + 1)]  # 包含默认的"0"
            for i, folder_name in enumerate(folder_names):
                folder_path = os.path.join(audio_dir, folder_name)
                try:
                    os.makedirs(folder_path, exist_ok=True)
                    print(f"成功创建文件夹: {folder_path}")

                    # 获取当前时间段的字幕
                    # if hasattr(self, 'asr_list') and self.asr_list:
                    #     start_time = 0 if i == 0 else sorted_timestamps[i - 1]
                    #     end_time = None if i == len(sorted_timestamps) else sorted_timestamps[i]

                        # lyrics = self.get_lyrics_in_time_range(start_time, end_time)
                        # lyric_path = os.path.join(folder_path, "lyric.txt")
                        # with open(lyric_path, "w", encoding="utf-8") as lyric_file:
                        #     lyric_file.write(lyrics)
                        # print(f"成功写入字幕: {lyric_path}")

                    config_data["videos"].append({
                        "video": f"[cut_type:dir]{ftp_path}/{{userid}}/{folder_name}/",
                        "digital_human": "",
                        "duration": round(durations[i], 2),
                        "clip_style": "only_video",
                        "video2": ""
                    })

                    config_data["videos_asynconf"].append({
                        "video": {"is_vertical":True, "cut_duration":5, "prompt":"Short video footage", "cut_count": 2},
                        "digital_human": {},
                        "video2": {},
                    })
                except Exception as e:
                    print(f"创建文件夹或写入字幕失败: {folder_path}，错误: {e}")

        try:
            os.makedirs(os.path.join(audio_dir, "topmask"), exist_ok=True)
            print(f"成功创建文件夹: topmask")
        except Exception as e:
            print(f"topmask文件夹创建失败: {e}")

        # 保存 config.json 文件
        try:
            config_path = os.path.join(audio_dir, "config.json")
            with open(config_path, "w", encoding="utf-8") as config_file:
                import json
                json.dump(config_data, config_file, ensure_ascii=False, indent=4)
            print(f"成功生成 config.json 文件: {config_path}")
        except Exception as e:
            print(f"生成 config.json 文件失败，错误: {e}")

        # 弹出创建成功提示框
        # message_dialog.show_custom_message_dialog(
        #     self,
        #     "模版创建成功！文件夹和 config.json 已生成。",
        #     "创建成功"
        # )

        self.window_close()

    def get_lyrics_in_time_range(self, start_ms, end_ms):
        """
        获取指定时间范围内的字幕文本。

        :param start_ms: 开始时间（毫秒），包含此时间。
        :param end_ms: 结束时间（毫秒），不包含此时间。
        :return: 时间范围内的字幕文本，按顺序拼接。
        """
        if not hasattr(self, 'asr_list') or not self.asr_list:
            return ""

        lyrics = []
        for item in self.asr_list:
            # 字幕的结束时间必须在范围内
            if (start_ms is None or item["finish"] > start_ms) and (end_ms is None or item["start"] < end_ms):
                lyrics.append(item["text"])

        return "\n".join(lyrics)

    def on_asr_button_click(self, event):
        """
        处理 ASR 按钮点击事件
        """
        self.show_loading("字幕加载中，请稍候...")  # 显示 Loading 和蒙层
        wx.CallLater(100, self.simulate_asr_call)  # 模拟异步调用 ASR
    
    def show_loading(self, message):
        """
        显示 Loading 提示和半透明蒙层
        """
        self.loading_overlay.SetSize(self.GetClientSize())  # 确保蒙层覆盖整个窗口
        self.loading_overlay.Show()
        self.loading_label.SetLabel(message)
        self.loading_label.CenterOnParent()  # 将 Loading 居中
        self.loading_label.Show()
        self.Layout()

    def hide_loading(self):
        """
        隐藏 Loading 提示和半透明蒙层
        """
        self.loading_label.Hide()
        self.loading_overlay.Hide()
        self.Layout()

    def aggregate_asr_results(self, asr_results, max_chars=80):
        """
        将 ASR 返回的结果聚合成较短的句子，尽量在句号断句。
        返回两个数组：纯文本和包含时间戳的数组。

        :param asr_results: 原始 ASR 返回的列表，每个元素包含 'text', 'start', 'finish'
        :param max_chars: 每个句子的最大字符数
        :return: (纯文本句子数组, 带时间戳的句子数组)
        """
        aggregated_with_timestamps = []
        aggregated_text_only = []
        current_sentence = {"text": "", "start": None, "finish": None}

        for word in asr_results:
            text = word["text"]
            start = word["start"]
            finish = word["finish"]

            # 如果当前句子为空，初始化起始时间戳
            if not current_sentence["text"]:
                current_sentence["start"] = start

            # 判断添加当前单词后是否超过最大字符数
            if len(current_sentence["text"]) + len(text) + 1 <= max_chars:
                # 不超过，添加到当前句子
                current_sentence["text"] += (" " if current_sentence["text"] else "") + text
                current_sentence["finish"] = finish

                # 如果遇到句号，强制结束当前句子
                if text.endswith("."):
                    aggregated_with_timestamps.append(current_sentence)
                    aggregated_text_only.append(current_sentence["text"])
                    # 开始新的句子
                    current_sentence = {"text": "", "start": None, "finish": None}
            else:
                # 超过，保存当前句子
                aggregated_with_timestamps.append(current_sentence)
                aggregated_text_only.append(current_sentence["text"])
                # 开始新的句子
                current_sentence = {"text": text, "start": start, "finish": finish}

        # 处理最后一个句子
        if current_sentence["text"]:
            aggregated_with_timestamps.append(current_sentence)
            aggregated_text_only.append(current_sentence["text"])

        return aggregated_text_only, aggregated_with_timestamps

    def simulate_asr_call(self):
        """
        调用 ASR 并获取结果
        """
        try:
            global MARKER_AUDIO_PATH
            import oss
            mp3_url = oss.loadURL(MARKER_AUDIO_PATH)
            s = requests.session()
            s.headers.update({
                'Connection':'close',
                'country':'us',
                'usertoken': '0cce7cfe3629e16ee9b3ea8563305d3a15c524804da1861db07c2c867d79da63'
            })
            params = {
                "file": mp3_url
            }
            global MARKER_LANGUAGE
            if MARKER_LANGUAGE:
                params["language"] = MARKER_LANGUAGE
            res = s.post("https://api.dalipen.com/aigc/text/speech_to_text", json=params, verify=False)
            s.close()
            if res.status_code == 200:
                result = res.json()
                if result["code"] == 0:
                    asr_data = result["data"]["lyric"]
                    text_list, asr_list = self.aggregate_asr_results(asr_data)
                    zh_text_list = translate.get(text_list, 'zh-CN')
                    # 按顺序赋值
                    for i, text in enumerate(zh_text_list):
                        item_text = asr_list[i]["text"]
                        asr_list[i]["text"] = text + " [" + item_text + "]"
                    
                    print(f"ryry_asr获取成功")
                    self.hide_loading()
                    self.asr_list = asr_list
                    self.draw_subtitle_end_lines()
                    self.update_subtitle()
        except Exception as e:
            print(f"ryry_asr失败，url={mp3_url}")
            print(e)

    def draw_subtitle_end_lines(self):
        """
        在波形图中，为每句字幕的结束时间画一条淡黄色的竖线
        """
        if not hasattr(self, 'asr_list'):
            return
        
        for item in self.asr_list:
            finish_ms = item["finish"]  # 毫秒
            # 转换成采样点
            finish_frame = int(finish_ms * self.sample_rate / 1000.0)
            
            line_obj = self.ax.axvline(finish_frame, color="#FFEE66", linestyle="-", linewidth=0.5)
            # 你可以把这些 line_obj 保存起来，如果需要后续删除或修改
        self.canvas.draw()

    def update_subtitle(self):
        """
        根据当前光标位置，查找对应字幕段并显示
        """
        if not hasattr(self, 'asr_list') or self.asr_list == None:
            # 如果还没拿到字幕数组，就不处理
            self.lbl_subtitle.SetLabel("")
            return

        current_ms = self.get_current_position_ms()  # 当前光标毫秒数

        # 遍历 asr_list，找 start <= current_ms < finish
        found_sub = None
        for item in self.asr_list:
            if item["start"] <= current_ms < item["finish"]:
                found_sub = item
                break

        if found_sub:
            self.lbl_subtitle.SetLabel(found_sub["text"])
        else:
            self.lbl_subtitle.SetLabel("")  # 不在任何字幕范围内，就空白
    
    def get_current_position_ms(self):
        current_frame = self.get_current_frame()
        return int(current_frame / self.sample_rate * 1000)
    
    def get_current_frame(self):
        """
        返回实时“光标采样点”。
        如果正在播放，则 = self.current_frame + 已播放采样数
        如果暂停或没播放，则 = self.current_frame
        """
        if self.is_playing:
            elapsed_time = time.time() - self.play_start_time
            played_samples = int(elapsed_time * self.sample_rate)
            return self.current_frame + played_samples
        else:
            return self.current_frame

    def on_segment_change(self, event):
        """
        用户切换自动分段选项
        """
        choice = int(self.segment_choices[self.segment_combo.GetSelection()])
        print(f"自动分段选项选择: {choice}")

        # 清空段落点
        for line in self.paragraph_lines:
            line.remove()  # 从图形中移除绿条
        self.paragraph_lines.clear()
        self.paragraph_timestamps.clear()

        if choice > 0:  # 如果不是"0"（不自动分）
            # 计算等分点
            segment_length = self.total_frames // choice
            for i in range(1, choice):
                timestamp = segment_length * i
                self.add_paragraph_point(timestamp)  # 调用时传入位置

        # 刷新画布
        self.canvas.draw()

    def on_close(self, event):
        global SCENE_CHOICES
        SCENE_CHOICES = []

        # 停止播放
        if self.play_obj:
            self.play_obj.stop()
            self.play_obj = None
        if hasattr(self, 'asr_list'):
            self.asr_list = None
        
        # 关闭当前窗口，恢复主窗口显示
        self.main_window.Show()
        self.Destroy()
    
    def window_close(self):
        global SCENE_CHOICES
        SCENE_CHOICES = []

        self.main_window.update_folder_list()
        
        # 停止播放
        if self.play_obj:
            self.play_obj.stop()
            self.play_obj = None
        if hasattr(self, 'asr_list'):
            self.asr_list = None
        
        # 关闭当前窗口，恢复主窗口显示
        self.main_window.Destroy()
        self.Destroy()

    def load_audio(self, path):
        if not is_wav_file(path):
            print(f"{path} 不是 WAV 文件，正在转换...")
            path = convert_to_wav(path)

        with wave.open(path, "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            self.sample_rate = wf.getframerate()
            n_frames = wf.getnframes()

            raw_data = wf.readframes(n_frames)
            wave_array = np.frombuffer(raw_data, dtype=np.int16)
            if n_channels > 1:
                wave_array = wave_array.reshape(-1, n_channels).mean(axis=1)

            # 归一化
            wave_array = wave_array.astype(np.float32)
            max_val = max(abs(wave_array).max(), 1e-9)
            wave_array /= max_val

            self.wave_data = wave_array
            self.total_frames = len(self.wave_data)

    def draw_waveform(self):
        self.ax.clear()
        self.ax.set_title("wave")
        self.ax.plot(np.arange(len(self.wave_data)), self.wave_data, color="blue")

        # 初始进度线（红线）
        self.line_cursor = self.ax.axvline(self.current_frame, color="red", linestyle="--", linewidth=2)

        self.ax.set_xlim(0, self.total_frames)
        ymin = min(self.wave_data) * 1.1
        ymax = max(self.wave_data) * 1.1 if max(self.wave_data) != 0 else 1
        self.ax.set_ylim(ymin, ymax)

        self.canvas.draw()

    def toggle_play(self, event):
        if not self.is_playing:
            self.start_play()
        else:
            self.stop_play()

    def start_play(self):
        self.is_playing = True
        self.btn_play.SetLabel("暂停")
        self.lbl_info.SetLabel("播放中")
        self.lbl_info.SetForegroundColour(wx.Colour("green"))

        frames_slice = self.wave_data[self.current_frame:]
        frames_int16 = (frames_slice * 32767).astype(np.int16)
        frames_bytes = frames_int16.tobytes()

        self.play_obj = sa.play_buffer(frames_bytes, 1, 2, self.sample_rate)
        self.play_start_time = time.time()

    def stop_play(self):
        self.is_playing = False
        self.btn_play.SetLabel("播放")
        self.lbl_info.SetLabel("暂停中")
        self.lbl_info.SetForegroundColour(wx.Colour("red"))

        if self.play_obj:
            self.play_obj.stop()
            self.play_obj = None

        # 更新 current_frame
        elapsed_time = time.time() - self.play_start_time
        self.current_frame += int(elapsed_time * self.sample_rate)

    def update_cursor(self, event):
        if self.is_playing:
            # 动态计算当前帧
            cursor_pos = self.get_current_frame()
            self.line_cursor.set_xdata(cursor_pos)

            if cursor_pos >= self.total_frames:
                # 循环播放：回到开头
                if self.play_obj:
                    self.play_obj.stop()
                    self.play_obj = None

                self.current_frame = 0
                self.is_playing = True
                self.btn_play.SetLabel("暂停")
                self.lbl_info.SetLabel("循环播放中")
                self.lbl_info.SetForegroundColour(wx.Colour("green"))

                frames_slice = self.wave_data[self.current_frame:]
                frames_int16 = (frames_slice * 32767).astype(np.int16)
                frames_bytes = frames_int16.tobytes()

                self.play_obj = sa.play_buffer(frames_bytes, 1, 2, self.sample_rate)
                self.play_start_time = time.time()

        self.canvas.draw()

        # 调用更新字幕
        self.update_subtitle()

    def on_mouse_down(self, event):
        """
        鼠标左键按下
        """
        # 如果按下的不是左键，直接返回
        if event.button != 1:
            return

        self.mouse_down = True  # 标记：左键被按下

        # 如果你仍想在“刚按下”就跳到对应位置，可继续保留：
        if event.xdata is not None:
            self.seek_to_x(event.xdata)
            self.canvas.draw_idle()
    
    def on_mouse_up(self, event):
        """
        鼠标左键松开
        """
        if event.button != 1:
            return
        self.mouse_down = False

    def on_left_up(self, event):
        """
        在 wx 下，如果要处理拖拽释放，可在这里做收尾
        """
        pass

    def on_mouse_move(self, event):
        """
        监听鼠标移动
        """
        if event.xdata is not None:
            xdata = event.xdata
            # 判断是否在波形范围内
            if 0 <= xdata <= self.total_frames:
                self.mouse_in_wave = True
                self.mouse_x = xdata
                # 如果按住鼠标左键拖拽，就移动红线
                if self.mouse_down:
                    self.seek_to_x(xdata)
                    self.canvas.draw_idle()
            else:
                self.mouse_in_wave = False
                self.mouse_x = None

    def on_key_pressed(self, event):
        keycode = event.GetKeyCode()
        # 一般 KeyCode 可能对应字母的 ASCII，如 a=65/A=65，s=83/S=83, ...
        # 这里简单处理小写 a/s/d 或空格
        if keycode in (65,):  # 'A'键
            self.add_paragraph_point()
        elif keycode in (83,):  # 'S'键
            self.add_mouse_paragraph_point()
        elif keycode in (68,):  # 'D'键
            self.remove_paragraph_point()
        elif keycode == wx.WXK_SPACE:
            self.toggle_play(None)

        # 刷新一下画面
        self.canvas.draw()

    def add_paragraph_point(self, timestamp=None):
        """
        添加段落点
        :param timestamp: 可选，指定的时间戳（以采样点为单位）
        """
        if timestamp is None:
            # 如果没有提供时间戳，使用当前播放位置
            current_sample = self.get_current_position()
        else:
            current_sample = int(timestamp)

        current_sample = max(0, min(current_sample, self.total_frames))  # 限制范围
        current_ms = int(current_sample / self.sample_rate * 1000)  # 转换为毫秒

        line_obj = self.ax.axvline(current_sample, color="green", linestyle="-", linewidth=2)
        self.paragraph_lines.append(line_obj)
        self.paragraph_timestamps.append(current_ms)

        print(f"添加段落点 => 采样点: {current_sample}, 时间: {current_ms} ms")

    def add_mouse_paragraph_point(self):
        """
        S 键：在鼠标位置添加段落点
        """
        if not self.mouse_in_wave:
            print("鼠标不在波形图区域，无法添加段落点...")
            return
        current_sample = int(round(self.mouse_x))
        current_sample = max(0, min(current_sample, self.total_frames))
        current_ms = int(current_sample / self.sample_rate * 1000)

        line_obj = self.ax.axvline(current_sample, color="green", linestyle="-", linewidth=2)
        self.paragraph_lines.append(line_obj)
        self.paragraph_timestamps.append(current_ms)

        print(f"鼠标段落点 => 采样点: {current_sample}, 时间: {current_ms} ms")

    def remove_paragraph_point(self):
        """
        D 键：撤销最近一次段落点
        """
        if not self.paragraph_lines:
            print("没有可撤销的段落点...")
            return

        line_obj = self.paragraph_lines.pop()
        line_obj.remove()
        removed_ts = self.paragraph_timestamps.pop()

        print(f"撤销段落点 => 时间: {removed_ts} ms")

    def get_current_position(self):
        """
        返回当前“播放位置”的采样点
        """
        if self.is_playing:
            elapsed_time = time.time() - self.play_start_time
            played_samples = int(elapsed_time * self.sample_rate)
            return self.current_frame + played_samples
        else:
            return self.current_frame

    def seek_to_x(self, x):
        x = max(0, min(x, self.total_frames))
        self.current_frame = int(x)
        if self.is_playing:
            self.restart_playback_from_current_position()
        else:
            self.line_cursor.set_xdata(self.current_frame)
            self.canvas.draw()
        
        # 调用更新字幕
        self.update_subtitle()

    def restart_playback_from_current_position(self):
        if self.play_obj:
            self.play_obj.stop()

        frames_slice = self.wave_data[self.current_frame:]
        frames_int16 = (frames_slice * 32767).astype(np.int16)
        frames_bytes = frames_int16.tobytes()

        self.play_obj = sa.play_buffer(frames_bytes, 1, 2, self.sample_rate)
        self.is_playing = True
        self.play_start_time = time.time()
        self.btn_play.SetLabel("暂停")
        self.lbl_info.SetLabel("播放中")
        self.lbl_info.SetForegroundColour(wx.Colour("green"))