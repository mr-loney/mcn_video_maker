import wx
import random
import string
import os
import wx.lib.scrolledpanel as scrolled
import ffmpeg  # 需要先pip安装 ffmpeg-python 或用subprocess调ffmpeg命令
import threading
import time
import concurrent.futures
import json
from pathlib import Path
from ryry import server_func
import sys
import platform

def get_ffplay_path():
    # 检测当前操作系统
    system_name = platform.system()

    if hasattr(sys, '_MEIPASS'):
        # 在 PyInstaller 打包环境下
        if system_name == "Windows":
            return os.path.join(sys._MEIPASS, 'ffplay', 'ffplay.exe')
        else:
            return os.path.join(sys._MEIPASS, 'ffplay', 'ffplay')
    else:
        # 未打包时，使用系统已安装的 ffmpeg
        # 如果在 Windows 下，常见可执行文件是 ffmpeg.exe
        # 如果在 macOS/Linux 下，则是 ffmpeg
        if system_name == "Windows":
            return 'ffplay.exe'
        else:
            return 'ffplay'

ffplay_path = get_ffplay_path()

class TTSGenerateFrame(wx.Frame):
    def __init__(self, parent, folder_path):
        super().__init__(parent, title="音频生成", size=(920, 800))
        self.parent = parent
        self.folder_path = folder_path  # 用于保存 req_XXX.json 的目录

        # 加载 audiolist 文件夹 => 供 Choice 使用
        # 这个文件夹相对于您项目的 paths, 也可做绝对路径
        base_dir = os.path.abspath(os.path.dirname(__file__))
        self.audiolist_dir = os.path.join(base_dir, "audiolist")
        self.all_audiolist = self.load_audiolist(self.audiolist_dir)

        # 生成随机后缀
        self.res_random_code, self.time_stamp = self.generate_random_code()

        self.text_normal_size = (700, 400)  # 非SeedVC 时文本框大小
        self.text_seedvc_size = (700, 60)   # SeedVC  时文本框大小

        # =========== scrolledPanel ============
        self.scrolled_panel = scrolled.ScrolledPanel(self, style=wx.VSCROLL|wx.HSCROLL)
        self.scrolled_panel.SetAutoLayout(True)
        self.scrolled_panel.SetupScrolling(scroll_x=True, scroll_y=True)

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 1) 对话人数
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(wx.StaticText(self.scrolled_panel, label="对话人数："), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.choice_num = wx.Choice(self.scrolled_panel, choices=["1","2","3","4"])
        self.choice_num.SetSelection(0)
        top_sizer.Add(self.choice_num, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.choice_num.Bind(wx.EVT_CHOICE, self.on_num_choice)
        main_sizer.Add(top_sizer, 0, wx.EXPAND)

        # 2) tts_api 下拉
        api_sizer = wx.BoxSizer(wx.HORIZONTAL)
        api_sizer.Add(wx.StaticText(self.scrolled_panel, label="tts_api:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.choice_tts_api = wx.Choice(self.scrolled_panel, choices=["MaskGCT","CosyVoice","OpenVoice","SeedVC","UVR5"])
        self.choice_tts_api.SetSelection(0)
        api_sizer.Add(self.choice_tts_api, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        main_sizer.Add(api_sizer, 0, wx.EXPAND)

        self.choice_tts_api.Bind(wx.EVT_CHOICE, self.on_tts_api_change)

        # 3) 多行文本
        lbl_text = wx.StaticText(self.scrolled_panel, label="TTS文本(多行，每行一条):")
        main_sizer.Add(lbl_text, 0, wx.ALL, 5)

        self.text_ctrl = wx.TextCtrl(self.scrolled_panel, style=wx.TE_MULTILINE, size=self.text_normal_size)
        main_sizer.Add(self.text_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        # =========== SeedVC 专属 sizer ============
        self.seedvc_sizer = wx.BoxSizer(wx.VERTICAL)
        # (A) 推理步数
        self.inference_label = wx.StaticText(self.scrolled_panel, label="推理步数:")
        self.inference_slider = wx.Slider(self.scrolled_panel, minValue=1, maxValue=200, value=10, style=wx.SL_HORIZONTAL)
        self.inference_val_label = wx.StaticText(self.scrolled_panel, label="10")
        row_infer = wx.BoxSizer(wx.HORIZONTAL)
        row_infer.Add(self.inference_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        row_infer.Add(self.inference_slider, 1, wx.EXPAND|wx.ALL, 5)
        row_infer.Add(self.inference_val_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.seedvc_sizer.Add(row_infer, 0, wx.EXPAND)
        self.inference_slider.Bind(wx.EVT_SLIDER, self.on_inference_slider_scroll)

        # (B) 音频速度
        self.speed_label = wx.StaticText(self.scrolled_panel, label="音频速度:")
        self.speed_slider = wx.Slider(self.scrolled_panel, minValue=50, maxValue=200, value=100, style=wx.SL_HORIZONTAL)
        self.speed_val_label = wx.StaticText(self.scrolled_panel, label="1.0")
        row_speed = wx.BoxSizer(wx.HORIZONTAL)
        row_speed.Add(self.speed_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        row_speed.Add(self.speed_slider, 1, wx.EXPAND|wx.ALL, 5)
        row_speed.Add(self.speed_val_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.seedvc_sizer.Add(row_speed, 0, wx.EXPAND)
        self.speed_slider.Bind(wx.EVT_SLIDER, self.on_speed_slider_scroll)

        # (C) CFG
        self.cfg_label = wx.StaticText(self.scrolled_panel, label="CFG值:")
        self.cfg_slider = wx.Slider(self.scrolled_panel, minValue=0, maxValue=100, value=70, style=wx.SL_HORIZONTAL)
        self.cfg_val_label = wx.StaticText(self.scrolled_panel, label="0.7")
        row_cfg = wx.BoxSizer(wx.HORIZONTAL)
        row_cfg.Add(self.cfg_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        row_cfg.Add(self.cfg_slider, 1, wx.EXPAND|wx.ALL, 5)
        row_cfg.Add(self.cfg_val_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.seedvc_sizer.Add(row_cfg, 0, wx.EXPAND)
        self.cfg_slider.Bind(wx.EVT_SLIDER, self.on_cfg_slider_scroll)

        # (D) F0音色 + 自动F0
        self.f0_condition_cb = wx.CheckBox(self.scrolled_panel, label="F0音色")
        self.f0_condition_cb.SetValue(False)
        self.seedvc_sizer.Add(self.f0_condition_cb, 0, wx.ALL, 5)
        self.f0_adjust_cb = wx.CheckBox(self.scrolled_panel, label="自动F0音色调节")
        self.f0_adjust_cb.SetValue(True)
        self.seedvc_sizer.Add(self.f0_adjust_cb, 0, wx.ALL, 5)

        # (E) 变调值 => -24~24
        self.pitch_label = wx.StaticText(self.scrolled_panel, label="变调值:")
        self.pitch_slider = wx.Slider(self.scrolled_panel, minValue=0, maxValue=48, value=24, style=wx.SL_HORIZONTAL)
        self.pitch_val_label = wx.StaticText(self.scrolled_panel, label="0")
        row_pitch = wx.BoxSizer(wx.HORIZONTAL)
        row_pitch.Add(self.pitch_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        row_pitch.Add(self.pitch_slider, 1, wx.EXPAND|wx.ALL, 5)
        row_pitch.Add(self.pitch_val_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.seedvc_sizer.Add(row_pitch, 0, wx.EXPAND)
        self.pitch_slider.Bind(wx.EVT_SLIDER, self.on_pitch_slider_scroll)

        self.seedvc_sizer.ShowItems(False)
        main_sizer.Add(self.seedvc_sizer, 0, wx.EXPAND)

        # =========== MaskGCT 专属 sizer ===========  
        self.maskgct_sizer = wx.BoxSizer(wx.VERTICAL)
        row_mg = wx.BoxSizer(wx.HORIZONTAL)

        # (1) audio_input_lang
        self.mg_audio_label = wx.StaticText(self.scrolled_panel, label="audio_input 语种:")
        self.mg_audio_input = wx.TextCtrl(self.scrolled_panel, value="en", size=(50, -1))
        row_mg.Add(self.mg_audio_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        row_mg.Add(self.mg_audio_input, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)

        # (2) text_input_lang
        self.mg_text_label = wx.StaticText(self.scrolled_panel, label="text_input 语种:")
        self.mg_text_input = wx.TextCtrl(self.scrolled_panel, value="en", size=(50, -1))
        row_mg.Add(self.mg_text_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        row_mg.Add(self.mg_text_input, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)

        # (3) TTS 时长 => audio_output_length
        self.mg_length_label = wx.StaticText(self.scrolled_panel, label="TTS 时长:")
        self.mg_length_input = wx.TextCtrl(self.scrolled_panel, value="-1", size=(50, -1))
        row_mg.Add(self.mg_length_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        row_mg.Add(self.mg_length_input, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)

        # (4) inference_step => 15~100
        self.mg_step_label = wx.StaticText(self.scrolled_panel, label="step(15~100):")
        self.mg_step_input = wx.TextCtrl(self.scrolled_panel, value="25", size=(50, -1))
        row_mg.Add(self.mg_step_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        row_mg.Add(self.mg_step_input, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)

        # (5) inference_step => 15~100
        self.mg_frequency_label = wx.StaticText(self.scrolled_panel, label="词频:")
        self.mg_frequency_input = wx.TextCtrl(self.scrolled_panel, value="40", size=(50, -1))
        row_mg.Add(self.mg_frequency_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        row_mg.Add(self.mg_frequency_input, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)

        self.maskgct_sizer.Add(row_mg, 0, wx.EXPAND)
        # 默认隐藏
        self.maskgct_sizer.ShowItems(True)
        main_sizer.Add(self.maskgct_sizer, 0, wx.EXPAND)

        # =========== [NEW] cosyvoice_sizer ===========
        self.cosyvoice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # 只放一个 speed 输入框 => 默认1.0 => audio_output_speed
        lbl_cosy_speed = wx.StaticText(self.scrolled_panel, label="音频速度:")
        self.cosy_speed_input = wx.TextCtrl(self.scrolled_panel, value="1.0", size=(50, -1))
        self.cosyvoice_sizer.Add(lbl_cosy_speed, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        self.cosyvoice_sizer.Add(self.cosy_speed_input, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)

        self.cosyvoice_sizer.ShowItems(False)
        main_sizer.Add(self.cosyvoice_sizer, 0, wx.EXPAND)

        # =========== 多角色面板 ===========
        self.roles_scrolled = scrolled.ScrolledPanel(self.scrolled_panel, style=wx.VSCROLL)
        self.roles_scrolled.SetAutoLayout(True)
        self.roles_scrolled.SetupScrolling(scroll_x=False, scroll_y=True)
        self.roles_sizer = wx.BoxSizer(wx.VERTICAL)
        self.roles_scrolled.SetSizer(self.roles_sizer)
        main_sizer.Add(self.roles_scrolled, 1, wx.EXPAND | wx.ALL, 5)

        # flow_output / local_path
        fl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        fl_sizer.Add(wx.StaticText(self.scrolled_panel, label="flow_output:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        default_flow_output = f"aigc_output/{self.res_random_code}_{self.time_stamp}"
        self.flow_output_ctrl = wx.TextCtrl(self.scrolled_panel, value=default_flow_output, size=(300, -1))
        fl_sizer.Add(self.flow_output_ctrl, 1, wx.ALL | wx.EXPAND, 5)

        fl_sizer.Add(wx.StaticText(self.scrolled_panel, label="local_path:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        default_local_path = os.path.join(self.folder_path, "reslib", self.res_random_code)
        self.local_path_ctrl = wx.TextCtrl(self.scrolled_panel, value=default_local_path, size=(300, -1))
        fl_sizer.Add(self.local_path_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(fl_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # bottom buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_ok = wx.Button(self.scrolled_panel, label="提交")
        self.btn_cancel = wx.Button(self.scrolled_panel, label="关闭")
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.btn_ok, 0, wx.ALL, 5)
        btn_sizer.Add(self.btn_cancel, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.btn_ok.Bind(wx.EVT_BUTTON, self.on_submit)
        self.btn_cancel.Bind(wx.EVT_BUTTON, lambda e: self.Close())

        self.scrolled_panel.SetSizer(main_sizer)
        self.roles_data = {}
        self.refresh_roles(1)

        self.SetSize((900, 800))
        self.CenterOnParent()
    
    def load_audiolist(self, dirpath):
        """
        从 /audiolist 文件夹中读取所有音频文件
        并返回一个列表 => ['','xxx.wav','test.mp3',...]
        这里的项目结构示例,您可改写
        """
        result = ['']  # 第一个是空 => 表示用户自定义
        if os.path.isdir(dirpath):
            for f in os.listdir(dirpath):
                full = os.path.join(dirpath, f)
                if os.path.isfile(full):
                    # 根据需要也可判断扩展名
                    result.append(f)
        return result

    # =========== Slider 回调 ===========
    def on_inference_slider_scroll(self, event):
        val = self.inference_slider.GetValue()
        self.inference_val_label.SetLabel(str(val))

    def on_speed_slider_scroll(self, event):
        val = self.speed_slider.GetValue()
        speed_f = round(val / 100.0, 2)
        self.speed_val_label.SetLabel(f"{speed_f}")

    def on_cfg_slider_scroll(self, event):
        val = self.cfg_slider.GetValue()
        cfg_f = round(val / 100.0, 2)
        self.cfg_val_label.SetLabel(f"{cfg_f}")

    def on_pitch_slider_scroll(self, event):
        val = self.pitch_slider.GetValue()
        shift = val - 24
        self.pitch_val_label.SetLabel(str(shift))

    def generate_random_code(self, length=5):
        suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        import time
        return f"res_{suffix}", time.strftime("%Y%m%d_%H%M%S")

    # =========== tts_api 下拉变化 ===========
    def on_tts_api_change(self, event):
        api_value = self.choice_tts_api.GetStringSelection()
        # 先统一隐藏
        self.seedvc_sizer.ShowItems(False)
        self.maskgct_sizer.ShowItems(False)

        # 文本框大小恢复
        self.text_ctrl.SetSize(self.text_normal_size)

        if api_value == "SeedVC":
            # 强制2人
            self.choice_num.SetSelection(1)
            self.refresh_roles(2)
            # 显示 seedvc
            self.seedvc_sizer.ShowItems(True)
            self.text_ctrl.SetMinSize(self.text_seedvc_size)
            self.text_ctrl.SetSize(self.text_seedvc_size)
        elif api_value == "MaskGCT":
            sel = self.choice_num.GetStringSelection()
            if sel:
                self.refresh_roles(int(sel))
            # 显示 maskgct
            self.maskgct_sizer.ShowItems(True)
            self.text_ctrl.SetMinSize(self.text_normal_size)
            self.text_ctrl.SetSize(self.text_normal_size)
        elif api_value == "CosyVoice":
            sel = self.choice_num.GetStringSelection()
            if sel:
                self.refresh_roles(int(sel))
            # 显示 maskgct
            self.cosyvoice_sizer.ShowItems(True)
            self.text_ctrl.SetMinSize(self.text_normal_size)
            self.text_ctrl.SetSize(self.text_normal_size)
        elif api_value == "UVR5":
            # 强制2人
            self.choice_num.SetSelection(0)
            self.refresh_roles(1)
            # 显示 seedvc
            self.seedvc_sizer.ShowItems(False)
            self.maskgct_sizer.ShowItems(False)
            self.cosyvoice_sizer.ShowItems(False)
            self.text_ctrl.SetMinSize(self.text_seedvc_size)
            self.text_ctrl.SetSize(self.text_seedvc_size)
        else:
            sel = self.choice_num.GetStringSelection()
            if sel:
                self.refresh_roles(int(sel))
            self.seedvc_sizer.ShowItems(False)
            self.maskgct_sizer.ShowItems(False)
            self.cosyvoice_sizer.ShowItems(False)

            self.text_ctrl.SetMinSize(self.text_normal_size)
            self.text_ctrl.SetSize(self.text_normal_size)

        self.scrolled_panel.Layout()
        self.scrolled_panel.SetupScrolling(scroll_x=True, scroll_y=True)

    # =========== 人数选择 + 刷新 roles ===========
    def on_num_choice(self, event):
        sel = self.choice_num.GetStringSelection()
        if sel:
            self.refresh_roles(int(sel))

    def on_role_audio_choice(self, event, rid, choice_ctrl):
        """
        当用户在下拉框里选择了某项:
        - 如果是空字符串 => 清空文本框 => 同时将音频图标隐藏(或设为无图)
        - 如果不是空 => 构造绝对路径 => roles_data[rid]["audio_path"] => 同步到文本框
        并更新图标
        """
        select_name = choice_ctrl.GetStringSelection().strip()
        icon_ctrl = self.roles_data[rid]["icon_ctrl"]
        path_ctrl = self.roles_data[rid]["path_ctrl"]
        
        if not select_name:
            # 为空 => 恢复空 => 让用户手动
            self.roles_data[rid]["audio_path"] = ""
            path_ctrl.SetValue("")
            # 隐藏/清空图标
            # 可以用 SetBitmap(wx.NullBitmap) 设为空图
            icon_ctrl.SetBitmap(wx.NullBitmap)
            return

        # 构造绝对路径 => self.audiolist_dir / select_name
        full_audio_path = os.path.join(self.audiolist_dir, select_name)
        if not os.path.isfile(full_audio_path):
            wx.LogWarning(f"音频不存在: {full_audio_path}")
            # 也可清空图标
            icon_ctrl.SetBitmap(wx.NullBitmap)
            return

        # 更新 audio_path / 文本框
        self.roles_data[rid]["audio_path"] = full_audio_path
        path_ctrl.SetValue(full_audio_path)

        # 更新图标 => 与 on_audio_selected 中类似
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_file = os.path.join(base_dir, "audio_icon.png")
        if os.path.isfile(icon_file):
            img = wx.Image(icon_file, wx.BITMAP_TYPE_PNG)
            w, h = icon_ctrl.GetSize()
            scaled = img.Scale(w, h, wx.IMAGE_QUALITY_HIGH)
            icon_ctrl.SetBitmap(wx.Bitmap(scaled))
        else:
            # 没有图标文件 => 也可清空
            icon_ctrl.SetBitmap(wx.NullBitmap)

    def refresh_roles(self, num_person):
        self.roles_sizer.Clear(delete_windows=True)
        for i in range(1, num_person+1):
            if i not in self.roles_data:
                random_name=''.join(random.choices(string.ascii_letters,k=5))
                self.roles_data[i]={
                    "role_name":random_name,
                    "audio_path":"",
                    "user_typed":False
                }
        remove_keys=[k for k in self.roles_data if k>num_person]
        for k in remove_keys:
            del self.roles_data[k]

        for i in range(1,num_person+1):
            row_sizer=wx.BoxSizer(wx.HORIZONTAL)

            tts_api = self.choice_tts_api.GetStringSelection()
            is_seedvc = (tts_api=="SeedVC" and num_person==2)
            is_uvr5 = (tts_api=="UVR5" and num_person==1)
            if is_seedvc:
                if i==1: lbl_txt="要述说的音频:"
                else:    lbl_txt="要克隆的音色:"
            else:
                lbl_txt=f"角色{i}名:"
            if is_uvr5:
                if i==1: lbl_txt="要分离的音频:"
            lbl_role=wx.StaticText(self.roles_scrolled,label=lbl_txt)
            row_sizer.Add(lbl_role,0,wx.ALIGN_CENTER_VERTICAL|wx.ALL,5)
            txt_role=wx.TextCtrl(self.roles_scrolled,size=(120,-1))
            txt_role.SetValue(self.roles_data[i]["role_name"])
            row_sizer.Add(txt_role,0,wx.ALIGN_CENTER_VERTICAL|wx.ALL,5)
            txt_role.Bind(wx.EVT_TEXT,lambda evt,idx=i:self.on_role_name_changed(evt,idx))

            # ========== [NEW] 下拉选择框 => audiolist ==========
            # 先copy self.all_audiolist => choices
            audio_choice = wx.Choice(self.roles_scrolled, choices=self.all_audiolist)
            audio_choice.SetSelection(0)  # 默认为第一项 => ''
            row_sizer.Add(audio_choice,0,wx.ALL|wx.ALIGN_CENTER_VERTICAL,5)
            # 当选择时 => on_role_audio_choice
            audio_choice.Bind(wx.EVT_CHOICE, lambda evt, rid=i, ch=audio_choice: self.on_role_audio_choice(evt, rid, ch))

            btn_file=wx.Button(self.roles_scrolled,label="选择音频/视频")
            row_sizer.Add(btn_file,0,wx.ALL|wx.ALIGN_CENTER_VERTICAL,5)
            def on_btn_file(evt,rid=i):
                self.choose_audio_file(rid)
            btn_file.Bind(wx.EVT_BUTTON,on_btn_file)

            icon_size=(50,50)
            icon_panel=wx.Panel(self.roles_scrolled,size=icon_size)
            icon_panel.SetBackgroundColour(wx.Colour(60,60,60))
            icon_bmp=wx.StaticBitmap(icon_panel,size=icon_size)
            row_sizer.Add(icon_panel,0,wx.ALL,5)

            drop_target=TTSAudioDropTarget(self,i,icon_bmp,self.on_audio_selected)
            icon_bmp.SetDropTarget(drop_target)

            existing_path=self.roles_data[i]["audio_path"]
            if existing_path:
                base_dir=os.path.dirname(os.path.abspath(__file__))
                icon_file=os.path.join(base_dir,"audio_icon.png")
                if os.path.isfile(icon_file):
                    img=wx.Image(icon_file,wx.BITMAP_TYPE_PNG)
                    w,h=icon_bmp.GetSize()
                    scaled=img.Scale(w,h,wx.IMAGE_QUALITY_HIGH)
                    icon_bmp.SetBitmap(wx.Bitmap(scaled))

            txt_path=wx.TextCtrl(self.roles_scrolled,size=(300,-1))
            txt_path.SetValue(existing_path)
            row_sizer.Add(txt_path,0,wx.ALIGN_CENTER_VERTICAL|wx.ALL,5)

            btn_play = wx.Button(self.roles_scrolled, label="试听", size=(35, -1))
            row_sizer.Add(btn_play, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
            # 绑定点击事件 => 调用 self.play_audio_3s
            btn_play.Bind(wx.EVT_BUTTON, lambda evt, rid=i: self.play_audio_3s(evt, rid))

            self.roles_data[i]["role_ctrl"]=txt_role
            self.roles_data[i]["icon_ctrl"]=icon_bmp
            self.roles_data[i]["path_ctrl"]=txt_path

            self.roles_sizer.Add(row_sizer,0,wx.EXPAND)

        self.roles_scrolled.Layout()
        self.roles_scrolled.SetupScrolling(scroll_x=False,scroll_y=True)

    def play_audio_3s(self, event, rid):
        """
        根据 rid，从 self.roles_data[rid]["path_ctrl"] 获取音频路径，
        用 ffplay 播放 3 秒后自动退出。
        """
        path = self.roles_data[rid]["path_ctrl"].GetValue().strip()
        if not path or not os.path.isfile(path):
            wx.MessageBox("请选择有效的音频文件", "错误", wx.OK | wx.ICON_ERROR)
            return

        import subprocess
        try:
            # 调用 ffplay 播放 3 秒后自动退出，不显示画面(-nodisp)
            # 如果没有安装 ffplay，则会报错
            subprocess.Popen([get_ffplay_path(), "-nodisp", "-autoexit", "-t", "3", path])
        except Exception as e:
            wx.MessageBox(f"播放失败: {e}", "错误", wx.OK | wx.ICON_ERROR)

    def on_role_name_changed(self, event, i):
        new_name=event.GetString()
        self.roles_data[i]["role_name"]=new_name
        self.roles_data[i]["user_typed"]=bool(new_name.strip())

    def choose_audio_file(self, idx):
        wildcard=(
            "Audio/Video (*.mp3;*.wav;*.ogg;*.flac;*.aac;"
            "*.mp4;*.mov;*.m4v;*.avi)|*.mp3;*.wav;*.ogg;"
            "*.flac;*.aac;*.mp4;*.mov;*.m4v;*.avi"
        )
        dlg=wx.FileDialog(self,"选择音频或视频",wildcard=wildcard,style=wx.FD_OPEN)
        if dlg.ShowModal()==wx.ID_OK:
            path=dlg.GetPath()
            self.on_audio_selected(idx,path)
        dlg.Destroy()

    def on_audio_selected(self, idx, local_path):
        if not os.path.isfile(local_path):
            return
        ext=os.path.splitext(local_path)[1].lower()
        audio_exts={".mp3",".wav",".ogg",".flac",".aac"}
        if ext not in audio_exts:
            final_audio=self.extract_audio(local_path)
        else:
            final_audio=local_path
        self.roles_data[idx]["audio_path"]=final_audio

        icon_ctrl=self.roles_data[idx]["icon_ctrl"]
        base_dir=os.path.dirname(os.path.abspath(__file__))
        icon_file=os.path.join(base_dir,"audio_icon.png")
        if os.path.isfile(icon_file):
            img=wx.Image(icon_file,wx.BITMAP_TYPE_PNG)
            w,h=icon_ctrl.GetSize()
            scaled=img.Scale(w,h,wx.IMAGE_QUALITY_HIGH)
            icon_ctrl.SetBitmap(wx.Bitmap(scaled))

        path_ctrl=self.roles_data[idx]["path_ctrl"]
        path_ctrl.SetValue(final_audio)

    def extract_audio(self, video_path):
        p=Path(video_path)
        out_path=str(p.with_name(p.stem+"_audio.mp3"))
        try:
            (
                ffmpeg
                .input(video_path)
                .output(out_path,format='mp3',acodec='libmp3lame',ac=2,ar='44100')
                .run(quiet=True)
            )
        except Exception as e:
            print(f"提取音频失败:{video_path},err={e}")
            return video_path
        return out_path

    def on_submit(self, event):
        self.busy_dlg=BusyDialog(self,"提交中，请稍后...")
        self.busy_dlg.Show()
        wx.GetApp().Yield()

        t=threading.Thread(target=self.do_submit_in_thread)
        t.start()

    def do_submit_in_thread(self):
        try:
            tts_api=self.choice_tts_api.GetStringSelection()
            text_lines=self.text_ctrl.GetValue().splitlines()
            flow_output=self.flow_output_ctrl.GetValue().strip()
            local_path=self.local_path_ctrl.GetValue().strip()

            # 构造多角色 audio_map
            audio_map={}
            idx_list=sorted(self.roles_data.keys())
            role_names=[]
            for i in idx_list:
                rname=self.roles_data[i]["role_ctrl"].GetValue().strip()
                if not rname:
                    rname=f"Role{i}"
                self.roles_data[i]["role_name"]=rname
                apath=self.roles_data[i]["path_ctrl"].GetValue().strip()
                audio_map[rname]=apath
                role_names.append(rname)

            # 构建 tts_inputs
            tts_inputs={}

            if tts_api=="SeedVC":
                # 强制2人
                if len(role_names)<2:
                    raise ValueError("SeedVC模式需要2人音频，请确认。")

                source_role=role_names[0]
                target_role=role_names[1]
                source_path=audio_map[source_role]
                target_path=audio_map[target_role]

                tts_inputs["audio_source"]=[source_path]
                tts_inputs["audio_target"]=[target_path]

                # 处理多行文本 => 如果有 #xx: => 保留，否则自动加 #source或 #target
                text_arr=self.build_text_with_roleprefix(text_lines, [source_role, target_role])

                tts_inputs["text_input"]=text_arr

                # 读取 seedvc slider
                tts_inputs["inference_step"]=self.inference_slider.GetValue()
                speed_val=self.speed_slider.GetValue()
                tts_inputs["audio_output_speed"]=round(speed_val/100.0,2)
                cfg_val=self.cfg_slider.GetValue()
                tts_inputs["inference_cfg"]=round(cfg_val/100.0,2)
                tts_inputs["f0_condition"]=self.f0_condition_cb.IsChecked()
                tts_inputs["f0_adjust"]=self.f0_adjust_cb.IsChecked()
                pitch_val=self.pitch_slider.GetValue()
                tts_inputs["pitch_shift"]=pitch_val-24

            elif tts_api=="MaskGCT":
                # 读取4个字段
                audio_input_lang=self.mg_audio_input.GetValue().strip() or "en"
                text_input_lang=self.mg_text_input.GetValue().strip() or "en"
                length_str=self.mg_length_input.GetValue().strip()
                step_str=self.mg_step_input.GetValue().strip()
                frequency_str=self.mg_frequency_input.GetValue().strip()
                try:
                    length_val=int(length_str)
                except:
                    length_val=-1
                try:
                    step_val=int(step_str)
                except:
                    step_val=25
                if step_val<15: step_val=15
                if step_val>100: step_val=100

                tts_inputs["audio_input_lang"]= audio_input_lang
                tts_inputs["text_input_lang"]=  text_input_lang
                tts_inputs["audio_output_length"]= length_val
                tts_inputs["inference_step"]= step_val
                tts_inputs["audio_output_frequency"]= int(frequency_str)

                # 角色 => audio_input
                tts_inputs["audio_input"]=audio_map
                # 文本 => 如果无 #xx: => 自动加 #role
                text_arr=self.build_text_with_roleprefix(text_lines, role_names)
                tts_inputs["text_input"]=text_arr

            elif tts_api=="CosyVoice":
                tts_inputs["audio_input"]=audio_map
                text_arr=self.build_text_with_roleprefix(text_lines, role_names)
                tts_inputs["text_input"]=text_arr
                tts_inputs["tts_mode"]=1
                # speed => audio_output_speed
                speed_str=self.cosy_speed_input.GetValue().strip()
                try:
                    cosy_speed_val=float(speed_str)
                except:
                    cosy_speed_val=1.0
                tts_inputs["audio_output_speed"]=cosy_speed_val
            
            elif tts_api=="UVR5":
                # tts_inputs["model_type"]="MDXC"
                # tts_inputs["model_name"]="MDX23C-8KFFT-InstVoc_HQ.ckpt"
                tts_inputs["auto_type"]=0
                tts_inputs["music_path"]=audio_map[role_names[0]]
                
            else:
                # F5
                tts_inputs["audio_input"]=audio_map
                text_arr=self.build_text_with_roleprefix(text_lines, role_names)
                tts_inputs["text_input"]=text_arr

            if tts_api=="UVR5":
                tts_data={
                    "uvr_api":"Auto",
                    "uvr_inputs":tts_inputs,
                    "uvr_output":flow_output,
                    "local_path":local_path
                }
            else:    
                tts_data={
                    "tts_api":tts_api,
                    "tts_inputs":tts_inputs,
                    "tts_output":flow_output,
                    "local_path":local_path
                }

            # FTP上传 => 并发 => 替换
            ftp_reslib_base="ftp://183.6.90.205:2221/mnt/NAS/mcn/reslib"
            import time
            time_stamp=time.strftime("%Y%m%d_%H%M%S")
            rand_str=''.join(random.choices(string.ascii_letters+string.digits,k=8))
            ftp_reslib_dir=f"{ftp_reslib_base}/{time_stamp}_{rand_str}"

            local_to_ftp={}
            for rname,apath in audio_map.items():
                if os.path.isfile(apath):
                    base=os.path.basename(apath)
                    ftp_path=f"{ftp_reslib_dir}/{base}"
                    local_to_ftp[apath]=ftp_path

            self.ftp_upload_concurrent(local_to_ftp)
            # 替换
            for rname,apath in audio_map.items():
                if apath in local_to_ftp:
                    audio_map[rname]=local_to_ftp[apath]

            if tts_api=="SeedVC":
                s_path=tts_inputs["audio_source"][0]
                t_path=tts_inputs["audio_target"][0]
                if s_path in local_to_ftp:
                    tts_inputs["audio_source"]=[local_to_ftp[s_path]]
                if t_path in local_to_ftp:
                    tts_inputs["audio_target"]=[local_to_ftp[t_path]]
            
            if tts_api=="UVR5":
                s_path=tts_inputs["music_path"]
                if s_path in local_to_ftp:
                    tts_inputs["music_path"]=local_to_ftp[s_path]

            req_data={
                "taskuuid":"test",
                "requests":[tts_data],
                "flows":[{
                    "flow_output":flow_output,
                    "local_path":local_path
                }]
            }
            
            if tts_api=="UVR5":
                api=server_func.AsyncTask("MCNUVRSepInOne",req_data)
            else:
                api=server_func.AsyncTask("MCNTTSGenInOne",req_data)
            taskuuid=api.call()
            req_data["taskuuid"]=taskuuid

            self.save_req_json(req_data)
            wx.CallAfter(self.on_submit_done,True,"")

        except Exception as e:
            wx.CallAfter(self.on_submit_done,False,str(e))

    def build_text_with_roleprefix(self, line_list, role_names):
        """
        如果行首没有 #xxx: 就自动加 #角色i:
        按角色数量循环 => 第1行 => role_names[0],第2行 => role_names[1],...,依次轮回
        如果用户手动写了 #xxxx: => 保留
        """
        import re
        pattern = re.compile(r"^#\S+?:")  # 以 #开头 + 若干非空格 + 冒号  => 如 #张三:
        text_arr=[]
        rcount=len(role_names)
        line_idx=0
        for line in line_list:
            line=line.strip()
            if not line:
                continue
            if pattern.match(line):
                # 用户自己写了 #xxx: => 保留
                text_arr.append(line)
            else:
                # 自动加
                rname = role_names[line_idx % rcount]
                text_arr.append(f"#{rname}:{line}")
                line_idx += 1
        return text_arr

    def on_submit_done(self,success,msg):
        if hasattr(self,"busy_dlg") and self.busy_dlg:
            self.busy_dlg.close_busy()
            self.busy_dlg=None

        if success:
            self.Close()
        else:
            wx.MessageBox(f"提交失败: {msg}","错误",wx.OK|wx.ICON_ERROR)

    def ftp_upload_concurrent(self, local_to_ftp):
        if not local_to_ftp:
            return
        max_workers=5
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map={}
            for lpath,fpath in local_to_ftp.items():
                fut=executor.submit(self.upload_single_file,lpath,fpath)
                future_map[fut]=(lpath,fpath)

            for fut in concurrent.futures.as_completed(future_map):
                lpath,fpath=future_map[fut]
                try:
                    fut.result()
                    print(f"上传成功: {lpath} => {fpath}")
                except Exception as ex:
                    print(f"上传失败: {lpath} => {fpath}, err={ex}")

    def upload_single_file(self, local_path, ftp_path):
        import ftplib
        prefix="ftp://183.6.90.205:2221"
        if not ftp_path.startswith(prefix):
            raise ValueError(f"不合法的 ftp_path: {ftp_path}")
        rel=ftp_path[len(prefix):]
        remote_dir=os.path.dirname(rel)
        remote_file=os.path.basename(rel)

        ftp_host="183.6.90.205"
        ftp_port=2221
        ftp_user="mcn"
        ftp_pass="meco@2024+"

        with ftplib.FTP() as ftp:
            ftp.connect(ftp_host,ftp_port,timeout=30)
            ftp.login(ftp_user,ftp_pass)
            self.ftp_makedirs(ftp,remote_dir)
            ftp.cwd(remote_dir)
            with open(local_path,"rb") as f:
                ftp.storbinary(f"STOR "+remote_file,f)

    def ftp_makedirs(self, ftp, remote_dir):
        if not remote_dir.startswith("/"):
            remote_dir="/"+remote_dir
        parts=remote_dir.strip("/").split("/")
        cur=""
        for p in parts:
            cur+="/"+p
            try:
                ftp.mkd(cur)
            except:
                pass

    def save_req_json(self, submission):
        reslib_dir = os.path.join(self.folder_path, "reslib")
        os.makedirs(reslib_dir, exist_ok=True)

        filename = f"{self.res_random_code}.json"
        req_path = os.path.join(reslib_dir, filename)
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(submission, f, ensure_ascii=False, indent=4)
        print(f"[TTS] 已写入: {req_path}")


class BusyDialog(wx.Dialog):
    def __init__(self, parent, message="请稍后..."):
        super().__init__(parent, title="", style=wx.STAY_ON_TOP | wx.NO_BORDER)
        parent.Enable(False)
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer()
        label = wx.StaticText(panel, label=message, size=(300, -1), style=wx.ALIGN_CENTER)
        sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 30)
        sizer.AddStretchSpacer()
        panel.SetSizer(sizer)
        self.SetMinSize((320, 180))
        self.Fit()
        self.CenterOnParent()

    def close_busy(self):
        parent = self.GetParent()
        if parent:
            parent.Enable(True)
        self.Destroy()

class TTSAudioDropTarget(wx.FileDropTarget):
    def __init__(self, parent_frame, role_index, icon_ctrl, on_audio_selected):
        super().__init__()
        self.parent_frame = parent_frame
        self.role_index = role_index
        self.icon_ctrl = icon_ctrl
        self.on_audio_selected = on_audio_selected

    def OnDropFiles(self, x, y, filenames):
        if not filenames:
            return False
        path = filenames[0]
        self.on_audio_selected(self.role_index, path)
        return True