import wx
import wx.lib.scrolledpanel as scrolled
import threading
import time
import os
import random
import string
import shutil
from audio_marker import AudioMarkerFrame

from pydub.silence import detect_nonsilent
import numpy as np
from pydub import AudioSegment

# 假设你已有的其他模块 (asrc, oss, audio_marker) 按需导入
# import asrc
# import oss

# ------------------------------------------------
# 全局变量 (与 Tkinter 版对应)
# ------------------------------------------------
MONTAGE_TYPE = None
AUDIO_PATH = None
LANGUAGE = "en-US"

def change_audio_speed(audio, speed_ratio):
    """
    只修改 frame_rate, 让播放时快/慢 (会“变调”)
    :param audio: pydub.AudioSegment
    :param speed_ratio: float, >1加速, <1减速
    :return: 变速后的AudioSegment
    """
    new_frame_rate = int(audio.frame_rate * speed_ratio)

    # 保护一下，避免 new_frame_rate 太低或太高
    MIN_RATE = 8000     # simpleaudio 通常支持的最小采样率
    MAX_RATE = 192000   # simpleaudio 通常支持的最大采样率
    if new_frame_rate < MIN_RATE:
        new_frame_rate = MIN_RATE
    elif new_frame_rate > MAX_RATE:
        new_frame_rate = MAX_RATE

    # _spawn可以在不复制数据的情况下生成新的AudioSegment
    return audio._spawn(audio.raw_data, overrides={
        "frame_rate": new_frame_rate
    }).set_frame_rate(new_frame_rate)

def create_empty_audio(duration_ms, output_path):
    """
    创建指定时长的空音频文件
    :param duration_ms: 时长（毫秒）
    :param output_path: 输出文件路径
    """
    silence_audio = AudioSegment.silent(duration=duration_ms)
    silence_audio.export(output_path, format="wav")
    print(f"生成空音频文件: {output_path}")

# ------------------------------------------------
# 处理音频的函数
# ------------------------------------------------
def editaudio(path, language="en-US", remove_silence=False, speed_ratio=1.0):
    """
    编辑音频的主功能
    :param path: 音频文件路径
    :param language: 语言参数 (暂时未使用)
    :param remove_silence: 是否需要剪除静音片段
    :param speed_ratio: 是否需要变速
    """

    print(f"开始处理音频: {path} (语言: {language}, 剪气口: {remove_silence}, 速度: {speed_ratio})")
    if remove_silence == False and speed_ratio == 1.0:
        return
    
    audio = AudioSegment.from_file(path)
    
    
    if remove_silence:
        silence_threshold = -100  # dBFS
        min_silence_len = 400     # ms

        nonsilent_ranges = detect_nonsilent(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_threshold
        )

        if not nonsilent_ranges:
            print("未检测到有效的非静音片段")
            edited_audio = audio
        else:
            edited_audio = AudioSegment.silent(duration=0)
            for start, end in nonsilent_ranges:
                print(f"保留片段: {start}ms - {end}ms")
                edited_audio += audio[start:end]
            audio = edited_audio
    else:
        edited_audio = audio

    # 调整变速
    if speed_ratio != 1.0:
        edited_audio = change_audio_speed(edited_audio, speed_ratio)

    # 统一将采样率设置为 44100Hz，避免 weird sample rate
    edited_audio = edited_audio.set_frame_rate(44100)

    output_path = path.rsplit(".", 1)[0] + "_edited.wav"
    edited_audio.export(output_path, format="wav")

    global AUDIO_PATH
    AUDIO_PATH = output_path
    global LANGUAGE
    LANGUAGE = language
    
    print(f"音频处理完成，输出文件: {output_path}")

# ------------------------------------------------
# 自定义拖拽类，用于接收文件
# ------------------------------------------------
class MyFileDropTarget(wx.FileDropTarget):
    def __init__(self, target_window):
        super().__init__()
        self.target_window = target_window

    def OnDropFiles(self, x, y, filenames):
        print("禁用拖拽")
        # 目前仅考虑单文件
        # if filenames:
        #     file_path = filenames[0]
        #     self.target_window.handle_file_async(file_path)
        return False

# ------------------------------------------------
# 主窗口
# ------------------------------------------------
class MainFrame(wx.Frame):
    def __init__(self, parent, music_path, folder_path):
        super().__init__(parent, title="MCN模版预处理", size=(450, 340),
                         style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER)
        self.has_audio_play = False
        self.SetBackgroundColour(wx.Colour("#333333"))

        self.folder_path = folder_path
        
        # 让窗口始终置顶（Windows上可用，其他平台可能略有差异）
        self.SetWindowStyle(self.GetWindowStyle() | wx.STAY_ON_TOP)

        # 面板，用于容纳控件
        panel = wx.Panel(self)
        panel.SetBackgroundColour("#444444")

        # 垂直布局
        self.vbox = wx.BoxSizer(wx.VERTICAL)

        # 拖拽/点击区域
        self.drop_panel = wx.Panel(panel, size=(300, 80))
        self.drop_panel.SetBackgroundColour("#333333") 

        # 给 drop_panel 添加一个 label
        self.drop_panel_label = wx.StaticText(self.drop_panel, 
                                              label="请设置音频选项\n然后点击下方按钮进入配置")
        # 设置字体样式
        label_font = self.drop_panel_label.GetFont()
        label_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.drop_panel_label.SetFont(label_font)

        panel_width, panel_height = self.drop_panel.GetSize()
        label_width, label_height = self.drop_panel_label.GetSize()

        # 计算水平和垂直居中的位置
        x = (panel_width - label_width) // 2
        y = (panel_height - label_height) // 2

        # 设置静态文本的位置
        self.drop_panel_label.SetPosition((x, y))
        self.drop_panel_label.Layout()

        # 注册文件拖拽
        drop_target = MyFileDropTarget(self)
        self.drop_panel.SetDropTarget(drop_target)

        # 绑定双击事件
        self.drop_panel.Bind(wx.EVT_LEFT_DOWN, self.on_drop_area_dblclick)
        self.vbox.Add(self.drop_panel, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10)

        # 动态添加音频时长输入区域
        self.duration_input_sizer = None
        if not music_path or music_path == None or music_path == "":  # AUDIO_PATH 为空时显示音频时长输入区域
            self.add_audio_duration_input(panel)

        # 语言选择
        hbox_lang = wx.BoxSizer(wx.HORIZONTAL)
        lang_text = wx.StaticText(panel, label="语言选择：")
        self.language_choices = ["en-US", "zh-CN", "ru-RU", "es-MX"]
        self.language_combo = wx.Choice(panel, choices=self.language_choices)
        self.language_combo.SetSelection(0)  # 默认选第一个
        hbox_lang.Add(lang_text, 0, wx.RIGHT, 5)
        hbox_lang.Add(self.language_combo, 1, wx.EXPAND)
        self.vbox.Add(hbox_lang, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)

        # 混剪模式
        hbox_mode = wx.BoxSizer(wx.HORIZONTAL)
        mode_text = wx.StaticText(panel, label="混剪模式：")
        self.mode_choices = ["普通混剪", "高级混剪", "多图模式"]
        self.mode_combo = wx.Choice(panel, choices=self.mode_choices)
        self.mode_combo.SetSelection(0)
        hbox_mode.Add(mode_text, 0, wx.RIGHT, 5)
        hbox_mode.Add(self.mode_combo, 1, wx.EXPAND)
        self.vbox.Add(hbox_mode, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)

        # 音频变速
        hbox_speed = wx.BoxSizer(wx.HORIZONTAL)
        speed_text = wx.StaticText(panel, label="音频变速：")
        self.speed_choices = ["x1.0", "x1.1", "x1.2", "x1.5", "x1.8", "x2.0"]
        self.speed_combo = wx.Choice(panel, choices=self.speed_choices)
        self.speed_combo.SetSelection(0)  # 默认选x1.0
        hbox_speed.Add(speed_text, 0, wx.RIGHT, 5)
        hbox_speed.Add(self.speed_combo, 1, wx.EXPAND)
        self.vbox.Add(hbox_speed, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)

        # 剪气口复选框
        self.remove_silence_chk = wx.CheckBox(panel, label="自动剪气口")
        self.remove_silence_chk.SetValue(False)
        self.vbox.Add(self.remove_silence_chk, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)

        # “处理中”提示
        self.loading_label = wx.StaticText(panel, label="", style=wx.ALIGN_CENTER)
        self.loading_label.SetForegroundColour(wx.Colour("red"))
        self.vbox.Add(self.loading_label, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)

        self.tpbutton = wx.Button(panel, label="开始配置")
        self.tpbutton.Bind(wx.EVT_BUTTON, lambda event, mp=music_path: self.show_template_settings(event, mp))
        self.vbox.Add(self.tpbutton, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)

        panel.SetSizer(self.vbox)

        self.start_time = 0
        self.processing_thread = None  # 用来存放子线程对象

        # self.Centre()
        self.CentreOnParent()
        self.Show()

    def add_audio_duration_input(self, panel):
        """
        添加音频时长输入区域
        """
        self.duration_input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        duration_text = wx.StaticText(panel, label="音频时长 (秒):")
        self.duration_input = wx.TextCtrl(panel, value="15")  # 默认值为 15 秒
        self.duration_input_sizer.Add(duration_text, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        self.duration_input_sizer.Add(self.duration_input, 1, wx.EXPAND)
        self.vbox.Add(self.duration_input_sizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)

    def on_drop_area_dblclick(self, event):
        """
        双击选择文件
        """
        print("禁用点击")
        # with wx.FileDialog(self, "选择音频文件", wildcard="音频文件 (*.wav;*.mp3;*.flac;*.aac;*.m4a)|*.wav;*.mp3;*.flac;*.aac;*.m4a|所有文件 (*.*)|*.*",
        #                    style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
        #     if fileDialog.ShowModal() == wx.ID_OK:
        #         file_path = fileDialog.GetPath()
        #         self.handle_file_async(file_path)
        # event.Skip()
    
    def show_template_settings(self, event, music_path):
        if self.has_audio_play == False:
            self.has_audio_play = True
            self.handle_file_async(music_path)

    def handle_file_async(self, file_path):
        """
        异步处理文件
        """
        print(f"获得文件路径: {file_path}")

        # 将混剪模式、音频路径存到全局变量
        global MONTAGE_TYPE, AUDIO_PATH
        MONTAGE_TYPE = self.mode_choices[self.mode_combo.GetSelection()]
        AUDIO_PATH = file_path
        print(f"当前混剪模式: {MONTAGE_TYPE}")
        print(f"当前音频路径: {AUDIO_PATH}")

        # 获取变速比率
        speed_selection = self.speed_choices[self.speed_combo.GetSelection()]
        speed_ratio = float(speed_selection[1:])  # 提取速度倍率（如 "x1.2" -> 1.2）

        # 显示“处理中”提示
        self.loading_label.SetLabel("处理中，请稍候...")
        self.loading_label.SetForegroundColour(wx.Colour("red"))
        self.start_time = time.time()
        """将 self.loading_label 在整个窗口内居中显示"""
        frame_width, frame_height = self.GetClientSize()
        label_width, label_height = self.loading_label.GetSize()
        # 计算水平和垂直居中的位置
        x = (frame_width - label_width) // 2
        y = self.loading_label.GetPosition().y
        # 设置静态文本的位置
        self.loading_label.SetPosition((x, y))

        # 禁用拖拽 & 双击
        self.drop_panel.SetDropTarget(None)
        self.drop_panel.Bind(wx.EVT_LEFT_DCLICK, lambda e: None)

        language = self.language_choices[self.language_combo.GetSelection()]
        remove_silence = self.remove_silence_chk.IsChecked()

        # 启动子线程
        self.processing_thread = threading.Thread(
            target=self.do_editaudio_in_thread,
            args=(file_path, language, remove_silence, speed_ratio),
            daemon=True
        )
        self.processing_thread.start()

    def do_editaudio_in_thread(self, path, language, remove_silence, speed_ratio):
        """
        子线程执行 audio edit（示例：剪气口）
        """
        try:
            time.sleep(0.1)
            editaudio(path, language, remove_silence, speed_ratio)
        finally:
            # 回到主线程做收尾
            wx.CallAfter(self.on_execute_done)

    def on_execute_done(self):
        # # 将提示更新成 "处理成功"
        # self.loading_label.SetLabel("处理成功!")
        # self.loading_label.SetForegroundColour(wx.Colour("green"))

        # # 恢复拖拽 & 双击
        # drop_target = MyFileDropTarget(self)
        # self.drop_panel.SetDropTarget(drop_target)
        # self.drop_panel.Bind(wx.EVT_LEFT_DCLICK, self.on_drop_area_dblclick)

        # # 打开新的“音频打点”窗口
        # global AUDIO_PATH
        # if AUDIO_PATH:
        #     # 清空提示
        #     self.loading_label.SetLabel("")
        #     # 打开音频打点窗口
        #     marker_frame = AudioMarkerFrame(self, AUDIO_PATH, MONTAGE_TYPE, LANGUAGE, self)
        #     marker_frame.Show()
        #     # 隐藏当前主窗口
        #     self.Hide()
        #     self.has_audio_play = False
        # else:
        #     print("警告：没有找到音频文件路径，无法打开打点窗口。")
        # 检查 global AUDIO_PATH
        global AUDIO_PATH
        if not AUDIO_PATH:
            try:
                # 获取用户输入的时长，默认值为 15 秒
                duration_seconds = int(self.duration_input.GetValue())
                if duration_seconds <= 0:
                    raise ValueError("音频时长必须为正整数")

                # 生成空音频文件
                output_path = os.path.join(self.folder_path, "empty_audio.wav")
                create_empty_audio(duration_seconds * 1000, output_path)
                AUDIO_PATH = output_path
            except ValueError:
                wx.MessageBox("请输入有效的音频时长（正整数）", "错误", wx.OK | wx.ICON_ERROR)
                return

        # 更新提示
        self.loading_label.SetLabel("处理成功!")
        self.loading_label.SetForegroundColour(wx.Colour("green"))

        # 打开新的“音频打点”窗口
        if AUDIO_PATH:
            self.loading_label.SetLabel("")
            marker_frame = AudioMarkerFrame(self, AUDIO_PATH, MONTAGE_TYPE, LANGUAGE, self)
            marker_frame.Show()
            self.Hide()
            self.has_audio_play = False
        else:
            print("警告：没有找到音频文件路径，无法打开打点窗口。")
    
    def update_folder_list(self):
        self.Parent.on_folder_selected(None)
        


# ------------------------------------------------
# 入口
# ------------------------------------------------
# if __name__ == "__main__":
#     app = wx.App(False)
#     frame = MainFrame(None)
#     app.MainLoop()