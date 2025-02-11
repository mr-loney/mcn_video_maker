import wx
import json
import os
import platform
import subprocess
from TemplateMain import MainFrame
from BatchCollection import BatchCollectionFrame
from comfiyUI import ImageGenerateFrame
from vcomfiyUI import VideoGenerateFrame
from hmcomfiyUI import HMGenerateFrame
import message_dialog
from ftplib import FTP
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import string
from as_panel import AdvancedSettingsPanel
from feishu import FeiShuDoc
from generateList import GenerateListFrame
from tts_panel import TTSGenerateFrame
from checkweb import CheckWebUpdates
from confirmDialog import ConfirmDialog
import sys
import ExportVideoWithRyry

LAST_FOLDER_PATH_FILE = "last_folder_path.json"  # 保存上次路径的文件名

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

def get_ffprobe_path():
    # 检测当前操作系统
    system_name = platform.system()

    if hasattr(sys, '_MEIPASS'):
        # 在 PyInstaller 打包环境下
        if system_name == "Windows":
            return os.path.join(sys._MEIPASS, 'ffprobe', 'ffprobe.exe')
        else:
            return os.path.join(sys._MEIPASS, 'ffprobe', 'ffprobe')
    else:
        # 未打包时，使用系统已安装的 ffmpeg
        # 如果在 Windows 下，常见可执行文件是 ffmpeg.exe
        # 如果在 macOS/Linux 下，则是 ffmpeg
        if system_name == "Windows":
            return 'ffprobe.exe'
        else:
            return 'ffprobe'

ffprobe_path = get_ffprobe_path()

class AdvancedSettingsDialog(wx.Dialog):
    """高级设置浮窗"""
    def __init__(self, parent, config_path):
        super().__init__(parent, title="提示词设置", size=(800, 600), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.config_path = config_path
        self.data = self.load_config()

        # 主面板
        main_panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 滚动区域
        self.scroll_panel = wx.ScrolledWindow(main_panel, style=wx.VSCROLL | wx.ALWAYS_SHOW_SB)
        self.scroll_panel.SetScrollRate(10, 10)  # 设置滚动步幅
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        # 内容段落
        if any(item.get("video") for item in self.data):
            scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="内容段落"), flag=wx.ALL, border=5)
            self.video_sizer = wx.BoxSizer(wx.VERTICAL)
            self.populate_section(self.scroll_panel, self.video_sizer, "video")
            scroll_sizer.Add(self.video_sizer, flag=wx.EXPAND)

        # 数字人段落
        if any(item.get("digital_human") for item in self.data):
            scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="数字人段落"), flag=wx.ALL, border=5)
            self.digital_human_sizer = wx.BoxSizer(wx.VERTICAL)
            self.populate_section(self.scroll_panel, self.digital_human_sizer, "digital_human")
            scroll_sizer.Add(self.digital_human_sizer, flag=wx.EXPAND)

        # 浮窗段落
        if any(item.get("video2") for item in self.data):
            scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="浮窗段落"), flag=wx.ALL, border=5)
            self.video2_sizer = wx.BoxSizer(wx.VERTICAL)
            self.populate_section(self.scroll_panel, self.video2_sizer, "video2")
            scroll_sizer.Add(self.video2_sizer, flag=wx.EXPAND)

        # 设置滚动区域的布局
        self.scroll_panel.SetSizer(scroll_sizer)
        scroll_sizer.Fit(self.scroll_panel)

        # 底部按钮区域
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        save_button = wx.Button(main_panel, label="确定")
        cancel_button = wx.Button(main_panel, label="取消")
        button_sizer.AddStretchSpacer()  # 添加弹性空间使按钮靠右对齐
        button_sizer.Add(save_button, flag=wx.ALL, border=5)
        button_sizer.Add(cancel_button, flag=wx.ALL, border=5)

        # 绑定按钮事件
        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)

        # 主布局
        main_sizer.Add(self.scroll_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)  # 滚动区域
        main_sizer.Add(button_sizer, flag=wx.EXPAND | wx.ALL, border=10)  # 按钮区域

        main_panel.SetSizer(main_sizer)
        self.CentreOnParent()

    def load_config(self):
        """加载 config.json"""
        try:
            with open(self.config_path, 'r') as file:
                config = json.load(file)
                return config.get("videos_asynconf", [])
        except Exception as e:
            wx.MessageBox(f"无法加载配置文件：{e}", "错误", wx.OK | wx.ICON_ERROR)
            return []

    def populate_section(self, panel, sizer, key):
        """根据字段内容生成 UI"""
        for i, item in enumerate(self.data):
            content = item.get(key)
            print(i, key, content)
            if not content:
                continue
            hbox = wx.BoxSizer(wx.HORIZONTAL)
            hbox.Add(wx.StaticText(panel, label=f"场景{i}:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

            # 提示词输入框
            hbox.Add(wx.StaticText(panel, label="视频提示词:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            prompt = wx.TextCtrl(panel, value=content.get("prompt", ""))
            hbox.Add(prompt, proportion=1, flag=wx.ALL | wx.EXPAND, border=5)
            content["prompt_ctrl"] = prompt

            # 生成时长下拉框
            hbox.Add(wx.StaticText(panel, label="时长:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            duration = wx.Choice(panel, choices=["5秒", "10秒"])
            duration.SetSelection(0 if content.get("cut_duration", 5) == 5 else 1)
            hbox.Add(duration, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            content["duration_ctrl"] = duration

            # 画布类型下拉框
            hbox.Add(wx.StaticText(panel, label="画布:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            canvas_type = wx.Choice(panel, choices=["竖屏", "横屏"])
            canvas_type.SetSelection(0 if content.get("is_vertical", True) else 1)  # 默认竖屏
            hbox.Add(canvas_type, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            content["vertical_ctrl"] = canvas_type

            # 生成次数输入框
            hbox.Add(wx.StaticText(panel, label="生成次数:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            count = wx.TextCtrl(panel, value=str(content.get("cut_count", 1)), size=(30, -1))
            hbox.Add(count, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            content["count_ctrl"] = count

            sizer.Add(hbox, flag=wx.EXPAND)

    def on_save(self, event):
        """保存编辑后的数据到配置文件"""
        try:
            # 加载原始配置文件
            with open(self.config_path, 'r') as file:
                config = json.load(file)
        except Exception as e:
            wx.MessageBox(f"加载配置文件时出错：{e}", "错误", wx.OK | wx.ICON_ERROR)
            return

        # 更新 videos_asynconf 字段
        for item in self.data:
            for key in ["video", "digital_human", "video2"]:
                if item.get(key):
                    ctrl = item[key]
                    ctrl["prompt"] = ctrl["prompt_ctrl"].GetValue()
                    ctrl["cut_duration"] = 5 if ctrl["duration_ctrl"].GetSelection() == 0 else 10
                    ctrl["is_vertical"] = ctrl["vertical_ctrl"].GetSelection() == 0
                    ctrl["cut_count"] = int(ctrl["count_ctrl"].GetValue())
                    # 删除临时控件引用
                    del ctrl["prompt_ctrl"], ctrl["duration_ctrl"], ctrl["vertical_ctrl"], ctrl["count_ctrl"]

        # 更新配置中的 videos_asynconf
        config["videos_asynconf"] = self.data

        try:
            # 保存更新后的配置文件
            with open(self.config_path, 'w') as file:
                json.dump(config, file, indent=4, ensure_ascii=False)
            self.EndModal(wx.ID_OK)
        except Exception as e:
            wx.MessageBox(f"保存配置文件时出错：{e}", "错误", wx.OK | wx.ICON_ERROR)

    def on_cancel(self, event):
        """取消编辑"""
        self.EndModal(wx.ID_CANCEL)

class MyFileDropTarget(wx.FileDropTarget):
    """自定义文件拖放目标"""
    def __init__(self, target_frame):
        super().__init__()
        self.target_frame = target_frame

    def OnDropFiles(self, x, y, filenames):
        """处理文件拖放事件"""
        if filenames:
            folder_path = filenames[0]
            if os.path.isdir(folder_path):
                self.target_frame.folder_picker.SetPath(folder_path)
                self.target_frame.update_folder_list(folder_path)
                self.target_frame.refresh_status()
                self.target_frame.save_last_folder_path(folder_path)  # 保存路径
            else:
                wx.MessageBox("请拖入一个文件夹！", "错误", wx.OK | wx.ICON_ERROR)
        return True

class FolderListApp(wx.Frame):
    """主应用窗口"""
    def __init__(self):
        super().__init__(None, title="🌈 小卤蛋 v1.1", size=(1300, 800))

        # 添加定时器
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer_refresh, self.timer)
        self.timer.Start(10000)  # 每10秒刷新一次
        
        self.folder_data = {}  # 存储每个文件夹的设置（是否虚拟账号、账号值）
        self.download_data = {}
        self.checkbox_data = {}

        self.base_root_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        self.checker = CheckWebUpdates([], self.base_root_path)
        self.check_thread = threading.Thread(target=self.checker.start_checking, daemon=True)  # 使用子线程进行定时检查
        self.check_thread.start()

        # 创建主面板
        panel = wx.Panel(self)

        # 文件夹选择布局
        folder_picker_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.folder_picker = wx.DirPickerCtrl(panel, message="选择文件夹", style=wx.DIRP_DEFAULT_STYLE)
        folder_picker_sizer.Add(self.folder_picker, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        # 添加“新建空模板”按钮
        new_template_button = wx.Button(panel, label="新建空模板")
        folder_picker_sizer.Add(new_template_button, flag=wx.EXPAND | wx.ALL, border=5)

        # 绑定事件
        new_template_button.Bind(wx.EVT_BUTTON, self.create_empty_template)
        
        # 列表框布局
        self.scroll_panel = wx.ScrolledWindow(panel, style=wx.VSCROLL | wx.ALWAYS_SHOW_SB)
        self.scroll_panel.SetScrollRate(20, 20)
        self.scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        self.scroll_panel.SetSizer(self.scroll_sizer)

        # 底部按钮区域
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        invert_button = wx.Button(panel, label="反选", size=(40, -1))
        refresh_button = wx.Button(panel, label="刷新")
        listen_button = wx.Button(panel, label="开始监听")  # 初始标签“开始监听”
        pick_button = wx.Button(panel, label="资源采集/预处理")
        btn_material_list = wx.Button(panel, label="工作流状态查询")
        submit_button = wx.Button(panel, label="提交模版")
        download_bak_button = wx.Button(panel, label="仅拉取原始资源")  # 新增拉取资源按钮
        download_button = wx.Button(panel, label="拉取全部资源")  # 新增拉取资源按钮
        export_button = wx.Button(panel, label="导出视频")
        self.export_state_button = wx.Button(panel, label="")

        self.is_listening = False
        
        button_sizer.Add(invert_button, flag=wx.RIGHT, border=10)
        button_sizer.Add(refresh_button, flag=wx.RIGHT, border=10)
        button_sizer.Add(listen_button, flag=wx.RIGHT, border=10)
        button_sizer.Add(pick_button, flag=wx.RIGHT, border=10)
        button_sizer.Add(btn_material_list, flag=wx.RIGHT, border=10)
        button_sizer.Add(submit_button, flag=wx.CENTER, border=10)
        button_sizer.Add(download_bak_button, flag=wx.LEFT, border=10)
        button_sizer.Add(download_button, flag=wx.LEFT, border=10)
        button_sizer.Add(export_button, flag=wx.LEFT, border=10)
        button_sizer.Add(self.export_state_button, flag=wx.LEFT, border=10)

        # 主布局
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(folder_picker_sizer, flag=wx.EXPAND)
        main_sizer.Add(self.scroll_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        main_sizer.Add(button_sizer, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)
        panel.SetSizer(main_sizer)

        # 事件绑定
        self.folder_picker.Bind(wx.EVT_DIRPICKER_CHANGED, self.on_folder_selected)
        invert_button.Bind(wx.EVT_BUTTON, self.on_invert)
        btn_material_list.Bind(wx.EVT_BUTTON, self.on_show_generate_list)
        pick_button.Bind(wx.EVT_BUTTON, self.on_pick_button_click)
        listen_button.Bind(wx.EVT_BUTTON, self.on_listen_button_click)
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh)
        submit_button.Bind(wx.EVT_BUTTON, self.on_submit)
        download_bak_button.Bind(wx.EVT_BUTTON, self.download_resources_bak)  # 绑定拉取资源事件
        download_button.Bind(wx.EVT_BUTTON, self.download_resources_nol)  # 绑定拉取资源事件
        #视频导出，管理器+事件监听
        export_button.Bind(wx.EVT_BUTTON, self.export_select_resources)
        self.export_state_button.Bind(wx.EVT_BUTTON, self.export_state_show)
        self.export_task_manager = ExportVideoWithRyry.ExportTaskManager(parent_window=self)
        self.Bind(ExportVideoWithRyry.EVT_EXPORT_COMPLETE, self.on_export_complete)
        self.export_state_button.Hide()
        
        self.Bind(wx.EVT_CLOSE, self.on_close_app)

        # 设置拖放功能
        drop_target = MyFileDropTarget(self)
        self.SetDropTarget(drop_target)

        # 加载上次文件夹路径
        self.load_last_folder_path()

        # 在这里创建 GenerateListFrame
        self.gen_list_frame = GenerateListFrame(self, self.folder_picker.GetPath())
        self.gen_list_frame.Show(False)  # 默认隐藏
        
        self.Show()
    
    def on_invert(self, event):
        for subfolder, data in self.folder_data.items():
            if data["checkbox"].GetValue() == True:
                c_bool = False
            else:
                c_bool = True
            data["checkbox"].SetValue(c_bool)
            self.checkbox_data[subfolder] = c_bool  # 更新状态
    
    def on_listen_button_click(self, event):
        btn = event.GetEventObject()
        if not self.is_listening:
            # 先更新UI
            dlg = ConfirmDialog(self, "‼️开始监听", "⚠️是否确定开始监听？\n该操作会在后台监听订阅博主的视频更新\n并把生成的视频自动发送到绑定账号")
            ret = dlg.ShowModal()
            dlg.Destroy()

            if ret == wx.ID_OK:
                self.is_listening = True
                btn.SetLabel("结束监听")
                # 先让界面刷新
                wx.GetApp().Yield()

                # 在子线程启动监听
                threading.Thread(target=self.start_listening_logic).start()
            else:
                return
        else:
            self.is_listening = False
            btn.SetLabel("开始监听")
            wx.GetApp().Yield()
            # 停止监听
            self.checker.updateEventlistener(False)

    def start_listening_logic(self):
        # 这里在子线程中执行真正的监听逻辑
        # 例如 self.checker.updateEventlistener(True)
        self.checker.updateEventlistener(True)
    
    def on_close_app(self, event):
        """
        当主窗口关闭时，可在这里执行收尾操作，
        比如停止 self.gen_list_frame 的子线程并销毁它，
        最后再关闭自己。
        """
        # 如果你在 ResToolsMain.py 中创建了 self.gen_list_frame:
        if self.gen_list_frame:
            # 让子线程安全退出
            self.gen_list_frame.stop_thread = True
            if self.gen_list_frame.thread.is_alive():
                self.gen_list_frame.thread.join()

            # 如果要彻底销毁 generateListFrame
            self.gen_list_frame.Destroy()
        
        # 销毁主窗口
        self.Destroy()
    
    def on_show_generate_list(self, event):
        # 同步一下 self.folder_picker.GetPath() 给 gen_list_frame
        self.gen_list_frame.root_folder = self.folder_picker.GetPath()
        # 先手动强制刷新一次
        self.gen_list_frame.force_refresh()
        self.gen_list_frame.Show(True)
    
    def on_pick_button_click(self, event):
        """
        点击“批量采集”按钮的事件
        """
        # 假设当前音频所在的父文件夹为：
        mfolder_picker = self.folder_picker.GetPath()
        subfolders_list = []

        for subfolder, data in self.folder_data.items():
            if not data["checkbox"].GetValue():
                continue
            subfolders_list.append(subfolder)

        # 弹出一个新的窗口并传入父文件夹路径
        dlg = BatchCollectionFrame(self, mfolder_picker, subfolders_list)
        dlg.Show()

    def create_empty_template(self, event):
        """新建空模板"""
        # 检查是否选择了文件夹
        folder_path = self.folder_picker.GetPath()
        if not folder_path:
            wx.CallAfter(message_dialog.show_custom_message_dialog, self, "请先选择一个有效的文件夹！", "错误")
            return
        
        # 弹窗输入模板名
        dlg = wx.TextEntryDialog(self, "请输入模板名：(绑账号:[edenworm]video1)", "新建空模板")
        if dlg.ShowModal() == wx.ID_OK:
            template_name = dlg.GetValue()
            if not template_name.strip():
                wx.CallAfter(message_dialog.show_custom_message_dialog, self, "模板名不能为空！", "错误")
                return

            # 检查是否有 *N 格式
            template_input = template_name
            if "*" in template_input:
                try:
                    base_name, multiplier = template_input.split("*")
                    base_name = base_name.strip()
                    multiplier = int(multiplier.strip())
                    if not base_name or multiplier <= 0:
                        raise ValueError
                except ValueError:
                    wx.CallAfter(message_dialog.show_custom_message_dialog, self, "输入格式错误！请使用 base_name*N 的格式，例如 template*4", "错误")
                    return
            else:
                base_name = template_input.strip()
                multiplier = 1  # 默认生成一次

            folder_path = self.folder_picker.GetPath()
            if not os.path.isdir(folder_path):
                wx.CallAfter(message_dialog.show_custom_message_dialog, self, "请先选择一个有效的文件夹！", "错误")
                return

            # 复制 resproject 文件夹到目标路径
            source_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resproject")
            if not os.path.exists(source_path):
                wx.CallAfter(message_dialog.show_custom_message_dialog, self, "找不到创建的资源！", "错误")
                return

            for i in range(multiplier):
                # 生成随机字符串和数字
                random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
                if multiplier == 1:
                    target_folder_name = f"{base_name}"
                else:
                    target_folder_name = f"{base_name}_{random_suffix}"
                target_path = os.path.join(folder_path, target_folder_name)

                if os.path.exists(target_path):
                    wx.CallAfter(message_dialog.show_custom_message_dialog, self, f"目标文件夹已存在：{target_folder_name}", "错误")
                    continue

                try:
                    # 递归复制文件夹
                    import shutil
                    shutil.copytree(source_path, target_path)
                    print(f"成功生成模板: {target_path}")
                except Exception as e:
                    wx.CallAfter(message_dialog.show_custom_message_dialog, self, f"复制模板文件夹失败：{e}", "错误")
                    continue

            # 重新加载文件夹列表
            try:
                self.update_folder_list(folder_path)
                self.refresh_status()
            except Exception as e:
                wx.CallAfter(message_dialog.show_custom_message_dialog, self, f"更新文件夹列表失败：{e}", "错误")
        dlg.Destroy()

    def download_resources_bak(self, event):
        self.only_bak = True
        self.download_resources(event)

    def download_resources_nol(self, event):
        self.only_bak = False
        self.download_resources(event)
    
    def on_export_complete(self, event):
        self.export_state_button.SetLabel(event.msg)
        if event.is_start and not self.export_state_button.IsShown():
            self.export_state_button.Show()  # 隐藏导出状态按钮
        if event.is_end and self.export_state_button.IsShown():
            self.export_state_button.Hide()  # 隐藏导出状态按钮
            wx.CallAfter(message_dialog.show_custom_message_dialog, self, f"点击关闭", "任务全部结束")
            task_window = ExportVideoWithRyry.TaskStatusWindow(self, self.export_task_manager)
            task_window.Show()
        self.export_state_button.Refresh()
        self.export_state_button.GetParent().Layout()
            
    def export_state_show(self,event):
        task_window = ExportVideoWithRyry.TaskStatusWindow(self, self.export_task_manager)
        task_window.Show()
        
    def export_select_resources(self, event):
        folder_path = self.folder_picker.GetPath()
        for subfolder, data in self.folder_data.items():
            if data["checkbox"].GetValue() == True:
                task = ExportVideoWithRyry.ExportTask(subfolder, data, data["mlabel"].LabelText, self.folder_picker)
                self.export_task_manager.add_task(task)
        self.export_task_manager.start()
        
    def download_resources(self, event):
        """拉取资源按钮事件"""
        folder_path = self.folder_picker.GetPath()
        tasks = []  # 存储所有需要处理的任务

        for subfolder, data in self.folder_data.items():
            if not data["checkbox"].GetValue():  # 如果复选框未被选中，跳过
                continue
            
            full_path = os.path.join(folder_path, subfolder)
            config_path = os.path.join(full_path, "config.json")
            run_path = os.path.join(full_path, "run.json")

            # 检查是否有 run.json 且 status 为 downloadable
            if not os.path.exists(run_path):
                continue

            with open(run_path, 'r') as run_file:
                try:
                    run_data = json.load(run_file)
                    if run_data.get("status") != "downloadable":
                        continue
                except json.JSONDecodeError:
                    continue

            # 检查是否存在 config.json
            if not os.path.exists(config_path):
                continue

            with open(config_path, 'r') as config_file:
                config = json.load(config_file)

            # 拼装 FTP 路径
            ftp_folder_name = config.get("ftp_folder_name", "")
            social_account = config.get("social_account", "")
            if not ftp_folder_name or not social_account:
                continue

            base_ftp_path = f"ftp://183.6.90.205:2221/mnt/NAS/mcn/aigclib/{ftp_folder_name}/{social_account}/"
            output_dir = os.path.join(full_path, "output")
            os.makedirs(output_dir, exist_ok=True)

            # 将任务加入任务列表
            tasks.append((subfolder, base_ftp_path, output_dir))

        # 使用线程处理下载任务
        if tasks:
            threading.Thread(target=self.download_with_threads, args=(tasks,)).start()
        else:
            # 弹出创建成功提示框
            wx.CallAfter(message_dialog.show_custom_message_dialog, self, "😂没有选中任何要拉取资源的文件夹！", "提示")

    def download_with_threads(self, tasks):
        """使用线程池并行下载"""
        max_threads = 3  # 最大线程数
        with ThreadPoolExecutor(max_threads) as executor:
            future_to_task = {
                executor.submit(self.download_task, task[0], task[1], task[2]): task
                for task in tasks
            }

            print(as_completed(future_to_task))

            for future in as_completed(future_to_task):
                subfolder, ftp_path, local_output_dir = future_to_task[future]
                try:
                    future.result()
                    print(f"下载完成: {ftp_path} -> {local_output_dir}")
                except Exception as e:
                    print(f"下载失败: {ftp_path}, 错误: {e}")

        # 弹出创建成功提示框
        wx.CallAfter(message_dialog.show_custom_message_dialog, self, "恭喜🎉🎉🎉,全部资源已更新!", "下载完成")

    def download_task(self, subfolder, ftp_path, local_output_dir):
        """单独下载某个子文件夹 => 内部用 5 线程并发下载其文件。"""
        self.download_data[subfolder] = True
        wx.CallAfter(self.update_folder_name, subfolder, is_downloading=True)

        # 1) 连接 FTP
        ftp = FTP()
        ftp.connect("183.6.90.205", 2221)
        ftp.login("mcn", "meco@2024+")

        # 2) 先收集主 ftp_path => all_files
        all_files = []
        self.collect_ftp_files(ftp, ftp_path, local_output_dir, all_files)

        # 3) 再检查 backup
        backup_ftp_path = ftp_path.rstrip("/") + "_backup/"
        try:
            base_path = backup_ftp_path.replace("ftp://183.6.90.205:2221", "").rstrip("/")
            ftp.cwd(base_path)  # 测试能否进入
            print(f"发现备份路径，开始收集: {backup_ftp_path}")
            self.collect_ftp_files(ftp, backup_ftp_path, local_output_dir, all_files)
        except:
            pass

        ftp.quit()

        # all_files 里现在有所有要下载的 (remote_file, local_file)
        # 4) 用内层 5线程并发下载
        with ThreadPoolExecutor(max_workers=5) as file_pool:
            future_map = {}
            for (rem, loc) in all_files:
                fut = file_pool.submit(self.download_single_file, rem, loc)
                future_map[fut] = (rem, loc)
            
            for fut in as_completed(future_map):
                rem, loc = future_map[fut]
                try:
                    fut.result()
                    print(f"文件下载完成: {rem} -> {loc}")
                except Exception as e:
                    print(f"下载出错: {rem}, err={e}")

        # 完成
        self.download_data[subfolder] = False
        wx.CallAfter(self.update_folder_name, subfolder, is_downloading=False)
        print(f"[download_task] {subfolder} 下载完毕, {len(all_files)} 个文件/目录.")

    def ftp_path_exists(self, ftp_path):
        """检查 FTP 路径是否存在"""
        try:
            ftp = FTP()
            ftp.connect("183.6.90.205", 2221)
            ftp.login("mcn", "meco@2024+")

            target_path = ftp_path.replace("ftp://183.6.90.205:2221", "").rstrip("/")
            ftp.cwd(target_path)
            ftp.quit()
            return True
        except Exception:
            return False
    
    def update_folder_name(self, subfolder, is_downloading):
        """更新文件夹名称"""
        data = self.folder_data.get(subfolder)
        download_data = self.download_data.get(subfolder)
        if not data:
            return
        
        # 获取文件夹路径和 config.json 的路径
        folder_path = os.path.join(self.folder_picker.GetPath(), subfolder)
        config_path = os.path.join(folder_path, "config.json")

        # 默认标签
        label_prefix = "[普通模版]"

        # 检查 config.json 是否存在并读取 is_create_human 字段
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as file:
                    config = json.load(file)
                    if config.get("is_create_human", False):  # 如果字段为 True
                        label_prefix = "[数字人模版]"
                    elif config.get("widget", "GenVideo_Template2") == "GenTemplateImage":
                        label_prefix = "[多图模版]"
            except Exception as e:
                print(f"读取配置文件失败: {config_path}, 错误: {e}")
        
        # 根据 is_downloading 状态更新标签
        if download_data == True:
            data["mlabel"].SetLabel(f"{label_prefix}{subfolder}-[拉取中...]")
        else:
            data["mlabel"].SetLabel(f"{label_prefix}{subfolder}")
        self.scroll_panel.Layout()

    def download_entire_ftp_directory(self, ftp_path, local_output_dir):
        """下载整个 FTP 文件夹及其内容"""
        try:
            # 连接到 FTP
            ftp = FTP()
            ftp.connect("183.6.90.205", 2221)
            ftp.login("mcn", "meco@2024+")

            # 切换到目标目录
            target_path = ftp_path.replace("ftp://183.6.90.205:2221", "").rstrip("/")
            ftp.cwd(target_path)

            # 遍历目标目录内容
            items = ftp.nlst()  # 列出目录内容

            # 如果只拉取_bak => 跳过纯数字目录
            if self.only_bak == True:
                import re
                pattern_digits = re.compile(r'^\d+$')  
                filtered_items = []
                for i in items:
                    # 如果匹配纯数字 => 跳过
                    if pattern_digits.match(i):
                        continue
                    # 否则保留
                    filtered_items.append(i)
                items = filtered_items

            for item in items:
                local_item_path = os.path.join(local_output_dir, item)
                
                try:
                    ftp.cwd(item)  # 如果可以进入，则是目录
                    os.makedirs(local_item_path, exist_ok=True)
                    # 递归下载子目录
                    self.download_entire_ftp_directory(
                        f"{ftp_path.rstrip('/')}/{item}", local_item_path
                    )
                    ftp.cwd("..")  # 返回上一级目录
                except Exception:
                    # 否则是文件
                    with open(local_item_path, "wb") as f:
                        ftp.retrbinary(f"RETR {item}", f.write)
                    print(f"文件下载完成: {ftp_path}/{item} -> {local_item_path}")

            ftp.quit()
        except Exception as e:
            print(f"下载失败: {ftp_path}, 错误: {e}")
    
    def collect_ftp_files(self, ftp, remote_dir, local_dir, all_files):
        """
        递归收集 remote_dir 下所有文件 => 追加到 all_files 列表里
        形式: all_files.append((remote_file_path, local_file_path)).
        """
        # remote_dir 可能带 "ftp://host:port", 去掉前缀
        base_path = remote_dir.replace("ftp://183.6.90.205:2221", "").rstrip("/")
        
        try:
            ftp.cwd(base_path)
        except:
            # 无法进入 => 视为不存在, 或不是目录
            return

        items = ftp.nlst()
        
        # 如果只拉取_bak => 跳过纯数字目录
        if self.only_bak:
            import re
            pattern_digits = re.compile(r'^\d+$')
            filtered = []
            for i in items:
                if pattern_digits.match(i):
                    continue
                filtered.append(i)
            items = filtered
        
        for item in items:
            if item in ('.', '..'):
                continue
            item_full_remote = base_path.rstrip('/') + '/' + item
            local_path = os.path.join(local_dir, item)

            try:
                ftp.cwd(item_full_remote)
                # 是目录 => 建本地目录 => 递归
                os.makedirs(local_path, exist_ok=True)
                self.collect_ftp_files(ftp, remote_dir.rstrip('/') + '/' + item, local_path, all_files)
                # 回到当前目录
                ftp.cwd(base_path)
            except:
                # 说明是文件 => 记录
                all_files.append((remote_dir.rstrip('/') + '/' + item, local_path))
    
    def download_single_file(self, remote_file_path, local_file_path):
        """
        单文件下载 => 每个文件一个线程。
        每次重新连接FTP, 以避免多线程cwd冲突。
        """
        try:
            ftp = FTP()
            ftp.connect("183.6.90.205", 2221)
            ftp.login("mcn", "meco@2024+")
            base_path = remote_file_path.replace("ftp://183.6.90.205:2221", "")
            dir_name = os.path.dirname(base_path)
            fname = os.path.basename(base_path)

            # 确保本地目录存在
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            ftp.cwd(dir_name)
            with open(local_file_path, "wb") as f:
                ftp.retrbinary(f"RETR " + fname, f.write)

            ftp.quit()
        except Exception as e:
            raise RuntimeError(f"下载失败: {remote_file_path}, err={e}")
    
    def on_timer_refresh(self, event):
        """定时器触发的刷新事件"""
        folder_path = self.folder_picker.GetPath()
        self.update_folder_list(folder_path)
        self.refresh_status()  # 刷新状态

    def load_last_folder_path(self):
        """加载上次使用的文件夹路径"""
        main_path = os.path.join(self.base_root_path, LAST_FOLDER_PATH_FILE)
        if os.path.exists(main_path):
            with open(main_path, 'r') as file:
                try:
                    last_folder = json.load(file).get("last_folder_path", "")
                    if os.path.isdir(last_folder):
                        self.folder_picker.SetPath(last_folder)
                        self.update_folder_list(last_folder)
                        self.refresh_status()
                except Exception as e:
                    wx.MessageBox(f"加载上次文件夹路径失败: {e}", "错误", wx.OK | wx.ICON_ERROR)

    def save_last_folder_path(self, folder_path):
        """保存当前使用的文件夹路径"""
        try:
            main_path = os.path.join(self.base_root_path, LAST_FOLDER_PATH_FILE)
            with open(main_path, 'w') as file:
                json.dump({"last_folder_path": folder_path}, file)
        except Exception as e:
            wx.MessageBox(f"保存文件夹路径失败: {e}", "错误", wx.OK | wx.ICON_ERROR)
    
    def on_folder_selected(self, event):
        """处理文件夹选择事件"""
        folder_path = self.folder_picker.GetPath()
        self.gen_list_frame.updateFolderPath(folder_path)
        self.update_folder_list(folder_path)
        self.refresh_status()
        self.save_last_folder_path(folder_path)  # 保存路径

    def update_folder_list(self, folder_path):
        """更新文件夹列表"""
        self.scroll_sizer.Clear(True)  # 清空当前列表
        # self.folder_data.clear()  # 清空当前设置数据

        if os.path.isdir(folder_path):
            subfolders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]

            subfolders.sort(
                key=lambda f: os.path.getctime(os.path.join(folder_path, f))
            )  # 按创建时间排序

            self.checker.update_list(folder_path, subfolders)

            for subfolder in subfolders:
                subfolder_path = os.path.join(folder_path, subfolder)
                config_path = os.path.join(subfolder_path, "config.json")
                run_path = os.path.join(subfolder_path, "run.json")
                label_text = f"[普通模版]{subfolder}"

                # 检查是否存在 config.json 文件并读取 is_create_human 字段
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r", encoding="utf-8") as file:
                            config = json.load(file)
                            if config.get("is_create_human", False):  # 如果字段为 True
                                label_text = f"[数字人模版]{subfolder}"
                            elif config.get("widget", "GenVideo_Template2") == "GenTemplateImage":
                                label_text = f"[多图模版]{subfolder}"
                    except Exception as e:
                        print(f"读取配置文件失败: {config_path}, 错误: {e}")

                download_data = self.download_data.get(subfolder)
                if download_data == True:
                    label_text = label_text + "-[拉取中...]"

                is_downloadable = False
                if os.path.exists(run_path):
                    with open(run_path, "r") as run_file:
                        try:
                            run_data = json.load(run_file)
                            if run_data.get("status") == "downloadable":
                                is_downloadable = True
                        except json.JSONDecodeError:
                            pass
                
                hbox = wx.BoxSizer(wx.HORIZONTAL)

                # 添加复选框
                checkbox = wx.CheckBox(self.scroll_panel)

                if subfolder in self.checkbox_data:
                    checkbox.SetValue(self.checkbox_data.get(subfolder))
                else:
                    checkbox.SetValue(False)  # 默认勾选可拉取资源的文件夹
                
                # if not is_downloadable:  # 如果文件夹可拉取资源，禁用复选框
                #     checkbox.Disable()
                # else:
                checkbox.Bind(wx.EVT_CHECKBOX, lambda event, sf=subfolder: self.on_checkbox_click(event, sf))
                hbox.Add(checkbox, flag=wx.ALL, border=6)
                
                label = wx.StaticText(self.scroll_panel, label=label_text)

                status_label = wx.StaticText(self.scroll_panel, label="")  # 状态栏
                
                tp_button = wx.Button(self.scroll_panel, label="模版配置", size=(60, -1))
                tp_button.Bind(wx.EVT_BUTTON, lambda event, sf=subfolder: self.show_template_settings(event, sf))
                image_button = wx.Button(self.scroll_panel, label="工作流", size=(50, -1))
                image_button.Bind(wx.EVT_BUTTON, lambda event, sf=subfolder: self.show_image_generator(event, sf))
                audio_button = wx.Button(self.scroll_panel, label="音频处理", size=(60, -1))
                audio_button.Bind(wx.EVT_BUTTON, lambda event, sf=subfolder: self.show_audio_generator(event, sf))
                video_button = wx.Button(self.scroll_panel, label="视频处理", size=(60, -1))
                video_button.Bind(wx.EVT_BUTTON, lambda event, sf=subfolder: self.show_video_generator(event, sf))
                hm_button = wx.Button(self.scroll_panel, label="口播处理", size=(60, -1))
                hm_button.Bind(wx.EVT_BUTTON, lambda event, sf=subfolder: self.show_hm_generator(event, sf))
                button = wx.Button(self.scroll_panel, label="场景设置", size=(60, -1))
                button.Bind(wx.EVT_BUTTON, lambda event, sf=subfolder: self.show_advanced_settings(event, sf))
                advanced_button = wx.Button(self.scroll_panel, label="高级设置", size=(60, -1))
                advanced_button.Bind(wx.EVT_BUTTON, lambda event, sf=subfolder: self.show_advanced_settings_panel(event, sf))
                copy_button = wx.Button(self.scroll_panel, label="复制", size=(40, -1))
                copy_button.Bind(wx.EVT_BUTTON,lambda evt, sf=subfolder: self.on_copy_folder_click(evt, sf))
                open_button = wx.Button(self.scroll_panel, label="打开", size=(40, -1))
                open_button.Bind(wx.EVT_BUTTON, lambda event, sf=subfolder: self.open_folder(event, sf))

                # 左侧的文件夹名称
                hbox.Add(label, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
                # 状态栏
                hbox.Add(status_label, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
                # 按钮靠右排列
                hbox.Add(tp_button, flag=wx.ALL, border=5)
                hbox.Add(image_button, flag=wx.ALL, border=5)
                hbox.Add(audio_button, flag=wx.ALL, border=5)
                hbox.Add(video_button, flag=wx.ALL, border=5)
                hbox.Add(hm_button, flag=wx.ALL, border=5)
                hbox.Add(button, flag=wx.ALL, border=5)
                hbox.Add(advanced_button, flag=wx.ALL, border=5)
                hbox.Add(copy_button, flag=wx.ALL, border=5)
                hbox.Add(open_button, flag=wx.ALL, border=5)

                self.scroll_sizer.Add(hbox, flag=wx.EXPAND)
                if not subfolder in self.folder_data:
                    self.folder_data[subfolder] = {"status_label": status_label, "mlabel": label, "checkbox": checkbox}
                self.folder_data[subfolder]["status_label"] = status_label
                self.folder_data[subfolder]["mlabel"] = label
                self.folder_data[subfolder]["checkbox"] = checkbox
        self.scroll_panel.Layout()
        self.scroll_panel.FitInside()
    
    def on_copy_folder_click(self, event, subfolder):
        """
        点击“复制文件夹”按钮时:
        1. 复制此文件夹 => subfolder + "_" + 5位随机字符串
        2. 删除目标文件夹中的 run.json
        3. 刷新列表
        """
        import shutil
        import random
        import string

        folder_path = self.folder_picker.GetPath()
        source_folder = os.path.join(folder_path, subfolder)
        if not os.path.isdir(source_folder):
            wx.MessageBox(f"源文件夹不存在: {source_folder}", "错误", wx.OK|wx.ICON_ERROR)
            return
        
        # 生成 5 位随机字符后缀，例如 "_A1b2C"
        random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        copy_folder_name = f"{subfolder}_{random_suffix}"  # 不再使用 "_copy"

        target_folder = os.path.join(folder_path, copy_folder_name)
        if os.path.exists(target_folder):
            wx.MessageBox(f"目标文件夹已存在: {copy_folder_name}", "错误", wx.OK|wx.ICON_ERROR)
            return
        
        # 执行复制 => shutil.copytree
        try:
            shutil.copytree(source_folder, target_folder)
        except Exception as e:
            wx.MessageBox(f"复制文件夹失败: {e}", "错误", wx.OK|wx.ICON_ERROR)
            return
        
        # 删除 run.json
        run_json_path = os.path.join(target_folder, "run.json")
        if os.path.exists(run_json_path):
            try:
                os.remove(run_json_path)
            except Exception as e:
                wx.MessageBox(f"删除 run.json 失败: {e}", "错误", wx.OK|wx.ICON_ERROR)
        
        # 刷新文件夹列表
        self.update_folder_list(folder_path)
        self.refresh_status()
    
    def show_audio_generator(self, event, subfolder):
        """
        点击“音频生成”时，打开 TTSGenerateFrame 窗口
        """
        folder_path = os.path.join(self.folder_picker.GetPath(), subfolder)
        frame = TTSGenerateFrame(self, folder_path)
        frame.Show()

    def show_image_generator(self, event, subfolder):
        """弹出图像生成窗口"""
        folder_path = os.path.join(self.folder_picker.GetPath(), subfolder)
        frame = ImageGenerateFrame(self, folder_path)
        frame.Show()
    
    def show_video_generator(self, event, subfolder):
        """弹出视频生成窗口"""
        folder_path = os.path.join(self.folder_picker.GetPath(), subfolder)
        frame = VideoGenerateFrame(self, folder_path)
        frame.Show()

    def show_hm_generator(self, event, subfolder):
        """弹出数字人生成窗口"""
        folder_path = os.path.join(self.folder_picker.GetPath(), subfolder)
        frame = HMGenerateFrame(self, folder_path)
        frame.Show()

    def on_checkbox_click(self, event, subfolder):
        """复选框点击事件处理"""
        checkbox = event.GetEventObject()
        self.checkbox_data[subfolder] = checkbox.GetValue()  # 更新状态
        print(f"Checkbox for {subfolder} is now {'checked' if checkbox.GetValue() else 'unchecked'}")  

    def show_advanced_settings_panel(self, event, subfolder_name):
        folder_path = os.path.join(self.folder_picker.GetPath(), subfolder_name)
        config_path = os.path.join(folder_path, "config.json")
        dialog = AdvancedSettingsPanel(self, config_path)
        dialog.ShowModal()
        dialog.Destroy()

    def refresh_status(self, force=False):
        """刷新每个文件夹的状态"""
        folder_path = self.folder_picker.GetPath()
        task_ids = []  # 存储需要查询状态的任务ID列表

        for subfolder, mdata in list(self.folder_data.items()):
            try:
                mdata["status_label"].GetLabel()
            except Exception as e:
                del self.folder_data[subfolder]  # 从字典中移除

        for subfolder, data in self.folder_data.items():
            full_path = os.path.join(folder_path, subfolder)
            config_path = os.path.join(full_path, "config.json")
            run_path = os.path.join(full_path, "run.json")

            if os.path.exists(run_path):
                with open(run_path, 'r') as file:
                    run_config = json.load(file)
                    if run_config.get("create_human_status") == "executing":
                        record_id_value = run_config.get("record_id", "")
                        if record_id_value:
                            task_ids.append(record_id_value)
                    elif not run_config.get("status") == "downloadable" and not run_config.get("status") == "error":
                        record_id_value = run_config.get("record_id", "")
                        if record_id_value:
                            task_ids.append(record_id_value)
                data["status_label"].SetLabel("模版执行中...")
                data["status_label"].SetForegroundColour(wx.Colour(255, 255, 0))  # 黄色

                with open(run_path, "r") as run_file:
                    try:
                        run_data = json.load(run_file)
                        if run_data.get("status") == "downloadable":
                            # 如果状态是 downloadable，直接设置为 "模版已生成,可下载"
                            data["status_label"].SetLabel("模版已生成,可拉取资源")
                            data["status_label"].SetForegroundColour(wx.Colour(0, 255, 0))  # 绿色

                            # if subfolder in self.checkbox_data:
                            #     self.folder_data[subfolder]["checkbox"].SetValue(self.checkbox_data.get(subfolder))
                            # else:
                            #     self.folder_data[subfolder]["checkbox"].SetValue(False) 
                            # self.folder_data[subfolder]["checkbox"].Enable()

                            if run_data.get("create_human_status") == "executing":
                                data["status_label"].SetLabel("模版已生成,可拉取资源(数字人生成中...)")
                                data["status_label"].SetForegroundColour(wx.Colour(0, 255, 0))  # 绿色
                            elif run_data.get("create_human_status") == "error":
                                data["status_label"].SetLabel("模版已生成,可拉取资源(数字人生成失败)")
                                data["status_label"].SetForegroundColour(wx.Colour(255, 0, 0))  # 红色
                            elif run_data.get("create_human_status") == "downloadable":
                                data["status_label"].SetLabel("模版已生成,可拉取资源(数字人生成成功)")
                                data["status_label"].SetForegroundColour(wx.Colour(0, 255, 0))  # 绿色
                            continue  # 跳过后续逻辑
                        if run_data.get("status") == "error":
                            # 如果状态是 error，直接设置为 "模版生成失败"
                            data["status_label"].SetLabel("模版生成失败")
                            data["status_label"].SetForegroundColour(wx.Colour(255, 0, 0))  # 红色
                            continue  # 跳过后续逻辑
                    except json.JSONDecodeError:
                        # 如果 run.json 文件损坏，标记为未知状态
                        data["status_label"].SetLabel("状态未知")
                        data["status_label"].SetForegroundColour(wx.Colour(255, 0, 0))  # 红色
                        continue  # 跳过后续逻辑
            elif "status_txt" in self.folder_data[subfolder] and self.folder_data[subfolder]["status_txt"] != "":
                data["status_label"].SetLabel(self.folder_data[subfolder]["status_txt"])
                data["status_label"].SetForegroundColour(self.folder_data[subfolder]["status_color"])  # 蓝色
                continue
            elif os.path.exists(config_path):
                data["status_label"].SetLabel("模版已准备")
                data["status_label"].SetForegroundColour(wx.Colour(0, 0, 255))  # 蓝色
            else:
                data["status_label"].SetLabel("模版未配置")
                data["status_label"].SetForegroundColour(wx.Colour(255, 0, 0))  # 红色

        # 如果需要强制刷新或定时查询，则调用服务端查询
        if force or self.timer.IsRunning():
            self.query_task_status(task_ids)
    
    def query_task_status(self, task_ids):
        """在子线程中查询任务状态并更新"""
        def fetch_status():
            try:
                feishu_doc = FeiShuDoc()
                status_list = feishu_doc.get_task_status(task_ids)  # 调用服务端接口获取状态
                wx.CallAfter(self.update_status_from_server, task_ids, status_list)
            except Exception as e:
                wx.CallAfter(wx.MessageBox, f"查询任务状态失败：{e}", "错误", wx.OK | wx.ICON_ERROR)

        threading.Thread(target=fetch_status).start()

    def update_status_from_server(self, task_ids, status_list):
        """根据服务端返回的状态更新UI"""
        folder_path = self.folder_picker.GetPath()
        for task_id, status in zip(task_ids, status_list):
            for subfolder, data in self.folder_data.items():
                full_path = os.path.join(folder_path, subfolder)
                # config_path = os.path.join(full_path, "config.json")
                run_path = os.path.join(full_path, "run.json")

                # 匹配对应的任务ID
                if os.path.exists(run_path):
                    with open(run_path, 'r') as file:
                        run_config = json.load(file)
                        if run_config.get("record_id", "") == task_id:
                            # 如果状态是“已完成”，更新 run.json
                            if status == "已完成":
                                run_data = {"status": "downloadable", "record_id": task_id}
                                with open(run_path, "w") as run_file:
                                    json.dump(run_data, run_file, ensure_ascii=False, indent=4)
                                # 更新状态为可下载
                                data["status_label"].SetLabel("模版已生成,可拉取资源")
                                data["status_label"].SetForegroundColour(wx.Colour(0, 255, 0))  # 绿色

                                # if subfolder in self.checkbox_data:
                                #     self.folder_data[subfolder]["checkbox"].SetValue(self.checkbox_data.get(subfolder))
                                # else:
                                #     self.folder_data[subfolder]["checkbox"].SetValue(False) 
                                # self.folder_data[subfolder]["checkbox"].Enable()
                            elif status == "已完成,数字人执行中":
                                run_data = {"status": "downloadable", "create_human_status": "executing", "record_id": task_id}
                                with open(run_path, "w") as run_file:
                                    json.dump(run_data, run_file, ensure_ascii=False, indent=4)
                                # 更新状态为可下载
                                data["status_label"].SetLabel("模版已生成,可拉取资源(数字人生成中...)")
                                data["status_label"].SetForegroundColour(wx.Colour(0, 255, 0))  # 绿色

                                # if subfolder in self.checkbox_data:
                                #     self.folder_data[subfolder]["checkbox"].SetValue(self.checkbox_data.get(subfolder))
                                # else:
                                #     self.folder_data[subfolder]["checkbox"].SetValue(False) 
                                # self.folder_data[subfolder]["checkbox"].Enable()
                            elif status == "已完成,数字人失败":
                                run_data = {"status": "downloadable", "create_human_status": "error", "record_id": task_id}
                                with open(run_path, "w") as run_file:
                                    json.dump(run_data, run_file, ensure_ascii=False, indent=4)
                                # 更新状态为可下载
                                data["status_label"].SetLabel("模版已生成,可拉取资源(数字人生成失败)")
                                data["status_label"].SetForegroundColour(wx.Colour(255, 0, 0))  # 红色

                                # if subfolder in self.checkbox_data:
                                #     self.folder_data[subfolder]["checkbox"].SetValue(self.checkbox_data.get(subfolder))
                                # else:
                                #     self.folder_data[subfolder]["checkbox"].SetValue(False) 
                                # self.folder_data[subfolder]["checkbox"].Enable()
                            elif status == "已完成,数字人成功":
                                run_data = {"status": "downloadable", "create_human_status": "downloadable", "record_id": task_id}
                                with open(run_path, "w") as run_file:
                                    json.dump(run_data, run_file, ensure_ascii=False, indent=4)
                                # 更新状态为可下载
                                data["status_label"].SetLabel("模版已生成,可拉取资源(数字人生成成功)")
                                data["status_label"].SetForegroundColour(wx.Colour(0, 255, 0))  # 绿色

                                # if subfolder in self.checkbox_data:
                                #     self.folder_data[subfolder]["checkbox"].SetValue(self.checkbox_data.get(subfolder))
                                # else:
                                #     self.folder_data[subfolder]["checkbox"].SetValue(False) 
                                # self.folder_data[subfolder]["checkbox"].Enable()
                            elif status == "已失败":
                                run_data = {"status": "error", "record_id": task_id}
                                with open(run_path, "w") as run_file:
                                    json.dump(run_data, run_file, ensure_ascii=False, indent=4)
                                # 更新状态为可下载
                                data["status_label"].SetLabel("模版生成失败")
                                data["status_label"].SetForegroundColour(wx.Colour(255, 0, 0))  # 红色

    def on_refresh(self, event):
        """刷新按钮点击事件"""
        # 重新加载文件夹列表
        folder_path = self.folder_picker.GetPath()
        self.update_folder_list(folder_path)

        # 强制调用状态刷新逻辑
        self.refresh_status(force=True)

    def on_submit(self, event):
        """提交任务按钮点击事件"""
        folder_path = self.folder_picker.GetPath()
        self.on_refresh(event)

        ready_folders = []

        for subfolder, data in self.folder_data.items():
            full_path = os.path.join(folder_path, subfolder)
            config_path = os.path.join(full_path, "config.json")
            run_path = os.path.join(full_path, "run.json")

            if not data["checkbox"].GetValue():  # 如果复选框未被选中，跳过
                continue

            if os.path.exists(config_path) and not os.path.exists(run_path):
                ready_folders.append(full_path)
                continue

            # 如果存在 run.json, 读取 run.json
            if os.path.exists(run_path):
                try:
                    with open(run_path, "r", encoding="utf-8") as run_file:
                        run_data = json.load(run_file)

                    # A) 如果 run_data["status"] 或 run_data["create_human_status"] 是 "error" => 可以重新提交
                    if run_data.get("status") == "error" or run_data.get("create_human_status") == "error":
                        ready_folders.append(full_path)
                        continue

                    # B) 如果 run_data["status"] == "downloadable" 并且
                    #    1. 没有 create_human_status 字段
                    #    2. 或 create_human_status == "downloadable"
                    #    => 删除 run.json, 让它重新提交
                    if run_data.get("status") == "downloadable":
                        chs = run_data.get("create_human_status")  # 可能为 None, 'downloadable', 'executing', etc.
                        if chs is None or chs == "downloadable":
                            # 删除 run.json
                            os.remove(run_path)
                            # 加入 ready_folders
                            ready_folders.append(full_path)
                            continue

                    # 其余情况 => 不再添加到 ready_folders (说明目前不允许再次提交)
                except json.JSONDecodeError as e:
                    print(f"无法解析 run.json 文件: {run_path}, 错误: {e}")
                    # 如果 JSON 破损，也可视为可重新提交
                    ready_folders.append(full_path)

        if ready_folders:
            # 先遍历每个准备提交的文件夹，进行 _pop 文件夹的处理
            for folder in ready_folders:
                self.process_pop_subfolders(folder)

            self.uploadTask(ready_folders)
        else:
            # 弹出创建成功提示框
            wx.CallAfter(message_dialog.show_custom_message_dialog, self, "🤣没有任何要提交的模版", "提示:")

    def process_pop_subfolders(self, folder_path):
        """
        扫描该文件夹下是否存在形如 {index}_pop 的子文件夹：
        1. 解析 index（将其转成整型，用于 config["videos"][index]["duration"]）
        2. 遍历_pop文件夹下不以 green_ 开头的文件
        3. 并发执行ffmpeg处理，输出1080×1980绿幕视频，同时缩小为1/3、随机摆放，变速到同duration
        """

        # 子线程池（最多3个并发）
        executor = ThreadPoolExecutor(max_workers=3)
        futures = []

        # 遍历folder_path下所有子文件夹
        for subf in os.listdir(folder_path):
            subf_path = os.path.join(folder_path, subf)
            if os.path.isdir(subf_path) and subf.endswith("_pop"):
                # 1. 获取index
                #   假设文件夹是形如 "0_pop", "3_pop" => 取下划线前面的数字
                try:
                    index_str = subf.split("_")[0]
                    index_val = int(index_str)
                except:
                    # 如果无法解析index，可根据项目需求决定忽略或报错
                    continue

                # 2. 读取 config.json => 获取 videos[index_val]["duration"]
                config_path = os.path.join(folder_path, "config.json")
                duration_seconds = 0
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r", encoding="utf-8") as cf:
                            cdata = json.load(cf)
                        # 如果 config 中有 videos 列表
                        if "videos" in cdata and len(cdata["videos"]) > index_val:
                            duration_seconds = cdata["videos"][index_val].get("duration", 0)
                    except:
                        pass

                # 3. 遍历子文件夹中不以 green_ 开头的文件 => 交给线程池处理
                for f in os.listdir(subf_path):
                    if f.startswith("green_"):
                        continue  # 跳过已经处理过的文件
                    source_file_path = os.path.join(subf_path, f)

                    # 判断一下是否图片或视频；此处仅示范，可按需做更精确的文件类型判断
                    # 例如: f.lower().endswith((".jpg",".png",".mp4",".mov")) 等
                    if os.path.isfile(source_file_path):
                        fut = executor.submit(
                            self.convert_to_green_screen,
                            source_file_path,
                            duration_seconds
                        )
                        futures.append(fut)

        # 4. 等待所有线程执行完再继续
        for future in as_completed(futures):
            # 如果任务中抛异常，这里可以捕获
            exc = future.exception()
            if exc:
                print(f"处理_pop文件夹时发生异常: {exc}")

        executor.shutdown()


    def convert_to_green_screen(self, input_path, target_duration):
        """
        用 ffmpeg 将 input_path 转成 1080×1980 的“绿幕”视频：
        - 缩放到原1/3大小，随机放置在画布(1080×1980)中，并留出一定边距
        - 变速/时长拉伸到 target_duration (如果 target_duration>0)
        - 最终输出临时文件 => 用 green_ 前缀改名覆盖原文件
        """

        # 这里示例把图片/视频统一当做视频来处理，若是图片，需要让它有指定时长
        # 在 ffmpeg 中可以用 -loop 1 -t xxxx 之类的方式让图片变成一个固定时长的视频
        # 简单示例，不区分图片/视频的情况，可根据需要再行改进

        # 准备好输出的临时文件
        # 假设当前同目录下输出 a_temp.mp4, 然后再覆盖
        dir_name = os.path.dirname(input_path)
        base_name = os.path.basename(input_path)
        # temp_output = os.path.join(dir_name, f"temp_{base_name}.mp4")
        # final_name = os.path.join(dir_name, f"green_{base_name}")

        # 如果源文件是图片 => 最终输出文件名改为 green_源文件名去掉后缀 + ".mp4"
        # 如果是视频，可决定是否仍用相同后缀，或者也统一用 .mp4
        if self.is_image_file(input_path):
            # 去掉原扩展，最终改为 .mp4
            # 先去掉扩展
            filename_no_ext = os.path.splitext(base_name)[0]
            final_name = os.path.join(dir_name, f"green_{filename_no_ext}.mp4")
            temp_output = os.path.join(dir_name, f"temp_{filename_no_ext}.mp4")
        else:
            # 如果你希望对视频也统一生成 mp4，可以和上面保持一致
            # 如果你想保留原始扩展，可以写下面这样:
            # final_name = os.path.join(dir_name, f"green_{base_name}")
            # temp_output = os.path.join(dir_name, f"temp_{base_name}")
            
            # 这里演示同一输出也用 mp4
            filename_no_ext = os.path.splitext(base_name)[0]
            final_name = os.path.join(dir_name, f"green_{filename_no_ext}.mp4")
            temp_output = os.path.join(dir_name, f"temp_{filename_no_ext}.mp4")

        # 给画布留边距
        margin = 50  
        canvas_w, canvas_h = 1080, 1980

        # 原内容缩放为 1/3（假设用 filter_complex 的 scale 来做）
        # 随机偏移 = [margin, canvas_w - scaled_w - margin], [margin, canvas_h - scaled_h - margin]
        # 由于我们不知道源图/源视频的宽高，需要动态获取，可以让 ffmpeg 的 filter_complex 来动态推算。
        # 这里举个例子：先缩放，然后再 overlay 到绿色画布上
        # 
        # "color=c=green" 生成一个全绿底 1080x1980
        # 再把输入缩放到1/3大小： scale=iw/3:ih/3
        # 再 overlay 到 (x,y)，x,y 需要先用随机值，但要先用一种 trick: 
        #   先把缩放结果临时命名为 [scaled], 
        #   让 ffmpeg 再次探测 [scaled] 的宽高，然后随机一个 x,y ...
        #
        # 由于 ffmpeg filter 中不太方便直接用 python 生成随机 x,y，这里示范思路是：
        #   * 先 probe 源文件的宽高 => 计算 1/3 => 在 python 这边生成 x,y => 再带入 filter_complex
        #
        # 如果你想在 ffmpeg 内部自动计算，需要更复杂的表达式，示例就不展开了。

        # 先用 ffprobe 获取原始宽高:
        origin_w, origin_h = self.ffprobe_get_width_height(input_path)
        if origin_w is None or origin_h is None:
            # 如果获取失败，就默认 720p 大小
            origin_w, origin_h = 1280, 720

        # ---------------------------
        # 第 1 步：先等比缩放到 width=1028
        # ---------------------------
        ratio = 1028 / origin_w
        temp_w = 1028
        temp_h = int(origin_h * ratio)

        scale_factor = random.uniform(0.4, 0.6)
        scaled_w = int(temp_w * scale_factor)
        scaled_h = int(temp_h * scale_factor)

        # scaled_w = int(origin_w * scale_factor)
        # scaled_h = int(origin_h * scale_factor)
        # 根据留边距，random 在 [margin, canvas_w - scaled_w - margin] 之间
        max_x = canvas_w - scaled_w - margin
        max_y = canvas_h - scaled_h - margin
        if max_x < margin or max_y < margin:
            # 如果 scaled 后还放不下，就把边距设为0
            margin = 0
            max_x = canvas_w - scaled_w
            max_y = canvas_h - scaled_h

        # 随机坐标
        overlay_x = random.randint(margin, max_x) if max_x>margin else 0
        overlay_y = random.randint(margin, max_y) if max_y>margin else 0

        # 组装 filter_complex
        # 1) 生成绿色底: [bg]
        # 2) [0:v] => scale=scaled_w:scaled_h => [scaled]
        # 3) overlay [bg]和[scaled] => [outv]
        #
        # 如果是静态图片，需要让它持续 target_duration
        #   => 在 input 上加 -loop 1 -t target_duration
        # 如果是视频 => 如果要变速到 target_duration，需要使用 setpts 或 atempo
        #   这里为了简单，先用 -t 强行截断/延长，真实场景中可结合 setpts/aresample。
        #
        # 下方命令仅是一个最简化示例，可能需要结合实际测试、排错。

        filter_str = (
            f"[0:v] scale={scaled_w}:{scaled_h} [scaled]; "
            f"color=c=green:s={canvas_w}x{canvas_h} [bg]; "
            f"[bg][scaled] overlay={overlay_x}:{overlay_y} [outv]"
        )

        # 根据是否有 target_duration 生成参数
        input_args = ["-i", input_path]
        if self.is_image_file(input_path):
            # 如果是图片，可能需要:
            # -loop 1 -t <duration> 来让它变成这么长的视频
            # 如果 duration=0，就给个默认时长
            if target_duration <= 0:
                target_duration = 5  # 比如默认5秒
            input_args = ["-loop", "1", "-t", str(target_duration), "-i", input_path]

        # -t target_duration 强制输出指定时长
        # 如果 target_duration <= 0 并且是原视频，可以不带 -t
        common_args = []
        if target_duration > 0:
            common_args += ["-t", str(target_duration)]

        command = [
            get_ffmpeg_path(),
            *input_args,
            "-y",                   # 覆盖输出
            "-vf", filter_str,      # 简单视频滤镜
            *common_args,
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            temp_output
        ]

        try:
            subprocess.run(command, check=True)
            print(f"已生成绿幕视频: {temp_output}")

            # 生成完毕 => 用 green_ 前缀命名 => 替换原文件
            # 先删掉同名 green_ 文件(如果已存在)
            if os.path.exists(final_name):
                os.remove(final_name)
            os.rename(temp_output, final_name)

            # 如果需要“替换掉原文件”，可以再删除原来的 input_path
            # 如果你想保留原文件，只需注释这行
            if os.path.exists(input_path):
                os.remove(input_path)

        except subprocess.CalledProcessError as e:
            print(f"ffmpeg处理失败: {e}")
            # 清理临时文件
            if os.path.exists(temp_output):
                os.remove(temp_output)


    def ffprobe_get_width_height(self, media_path):
        """
        使用 ffprobe 获取视频或图片宽高，返回 (w,h)，获取失败返回 (None, None)
        """
        import shlex
        import json

        if not os.path.isfile(media_path):
            return (None, None)
        
        mffprobe_path = get_ffprobe_path()
        cmd = f'{mffprobe_path} -v quiet -print_format json -show_streams {shlex.quote(media_path)}'
        try:
            cp = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            probe_result = json.loads(cp.stdout)
            streams = probe_result.get("streams", [])
            for st in streams:
                # 只看 video stream
                if st.get("codec_type") == "video":
                    w = st.get("width")
                    h = st.get("height")
                    return (w, h)
            return (None, None)
        except:
            return (None, None)


    def is_image_file(self, path):
        """
        简单判断是否图片扩展名
        """
        lower_name = path.lower()
        exts = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"]
        return any(lower_name.endswith(e) for e in exts)

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

    def update_config_if_duplicate(self, folders):
        """
        按文件夹创建时间排序后，检查是否存在重复的 ftp_folder_name，
        如果重复则更新为唯一的 ftp_folder_name，并保存更新后的 config.json。
        
        :param folders: 需要检查的文件夹路径列表
        """
        # 排序文件夹，按创建时间
        folders = sorted(folders, key=lambda folder: os.path.getctime(folder))

        # 缓存已存在的 ftp_folder_name
        ftp_folder_name_cache = set()

        for folder in folders:
            config_path = os.path.join(folder, "config.json")
            run_path = os.path.join(folder, "run.json")
            if os.path.exists(run_path):
                continue
            
            if not os.path.exists(config_path):
                continue

            with open(config_path, 'r', encoding='utf-8') as file:
                try:
                    config = json.load(file)
                except json.JSONDecodeError:
                    print(f"无法解析 {config_path}，跳过此文件")
                    continue

            # 获取当前的 ftp_folder_name
            ftp_folder_name = config.get("ftp_folder_name")
            if not ftp_folder_name:
                print(f"{config_path} 中缺少 ftp_folder_name，跳过此文件")
                continue

            # 如果发现重复
            # if ftp_folder_name in ftp_folder_name_cache:
            print(f"发现重复的 ftp_folder_name: {ftp_folder_name}，更新为新的唯一值")
            parent_folder = os.path.basename(folder)
            new_ftp_folder_name = self.generate_unique_filename(parent_folder)
            ftp_folder_name_cache.add(new_ftp_folder_name)

            # 更新 config.json 的 ftp_folder_name 和所有相关路径
            config["ftp_folder_name"] = new_ftp_folder_name
            keys_to_update = ["videos", "use_video_subtitle", "audio", "videos_asynconf"]

            def update_path(path):
                if ftp_folder_name in path:
                    return path.replace(ftp_folder_name, new_ftp_folder_name)
                return path

            # 更新路径
            if "videos" in config:
                # 如果 widget 字段为 "GenTemplateImage"
                if config.get("widget") == "GenTemplateImage":
                    for i in range(len(config["videos"])):
                        video_path = config["videos"][i]
                        # 找到本地对应的目录路径
                        local_dir = os.path.join(folder, os.path.basename(video_path))
                        if not os.path.isdir(local_dir):
                            print(f"目录 {local_dir} 不存在，跳过")
                            continue

                        # 遍历目录中的所有图片文件
                        for root, _, files in os.walk(local_dir):
                            for file_name in files:
                                # 检查文件扩展名是否为图片类型
                                if file_name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif")):
                                    # 判断文件名是否以 _keepimg 结尾
                                    if not file_name.endswith("_keepimg.jpg") and not file_name.endswith("_keepimg.jpeg") and not file_name.endswith("_keepimg.png") and not file_name.endswith("_keepimg.bmp") and not file_name.endswith("_keepimg.gif"):
                                        # 修改文件名为 xxx_keepimg
                                        base_name, ext = os.path.splitext(file_name)
                                        new_file_name = f"{base_name}_keepimg{ext}"
                                        old_file_path = os.path.join(root, file_name)
                                        new_file_path = os.path.join(root, new_file_name)
                                        try:
                                            os.rename(old_file_path, new_file_path)
                                            print(f"文件名已修改: {old_file_path} -> {new_file_path}")
                                        except Exception as e:
                                            print(f"修改文件名失败: {old_file_path}, 错误: {e}")

                        # 更新路径
                        config["videos"][i] = update_path(video_path)
                else:
                    # 原逻辑：遍历 "video", "digital_human", "video2" 字段
                    for video in config["videos"]:
                        for key in ["video", "digital_human", "video2"]:
                            if key in video:
                                video[key] = update_path(video[key])

            if "use_video_subtitle" in config:
                config["use_video_subtitle"] = update_path(config["use_video_subtitle"])

            if "audio" in config:
                config["audio"] = update_path(config["audio"])

            if "videos_asynconf" in config:
                for asynconf in config["videos_asynconf"]:
                    for key in ["video", "digital_human", "video2"]:
                        if key in asynconf and "prompt" not in asynconf[key]:
                            for sub_key in asynconf[key]:
                                asynconf[key][sub_key] = update_path(asynconf[key][sub_key])

            # 保存更新后的 config.json
            with open(config_path, 'w', encoding='utf-8') as file:
                json.dump(config, file, ensure_ascii=False, indent=4)
            print(f"{config_path} 已更新并保存")
            # else:
            #     ftp_folder_name_cache.add(ftp_folder_name)
                
    def uploadTask(self, folders):
        """提交预处理任务"""
        # 启动一个新线程执行上传任务
        thread = threading.Thread(target=self._uploadTaskThread, args=(folders,))
        thread.start()
    
    def _uploadTaskThread(self, folders):
        """实际执行上传任务的线程，支持并行处理"""
        self.update_config_if_duplicate(folders)

        ftp_config = {
            "host": "183.6.90.205",
            "port": 2221,
            "username": "mcn",
            "password": "meco@2024+",
        }

        max_parallel_uploads = 3  # 最大并行上传数
        with ThreadPoolExecutor(max_workers=max_parallel_uploads) as executor:
            future_to_folder = {
                executor.submit(self.upload_single_folder, ftp_config, folder): folder
                for folder in folders
            }

            for future in future_to_folder:
                folder = future_to_folder[future]
                try:
                    future.result()  # 等待线程完成
                except Exception as e:
                    wx.CallAfter(wx.MessageBox, f"处理文件夹 {folder} 时发生错误：{e}", "错误", wx.OK | wx.ICON_ERROR)

    def upload_to_ftp(self, ftp_config, local_path, ftp_path):
        """将本地文件或目录上传到 FTP"""
        try:
            ftp = FTP()
            ftp.connect(ftp_config["host"], ftp_config["port"])
            ftp.login(ftp_config["username"], ftp_config["password"])

            # 提取 FTP 目录
            ftp_dir = os.path.dirname(ftp_path.replace("ftp://183.6.90.205:2221", ""))
            ftp_basename = os.path.basename(ftp_path.rstrip("/"))

            # 确保 FTP 目录存在
            self.ensure_ftp_directory(ftp, ftp_dir)

            if os.path.isdir(local_path):
                # 上传整个目录
                for root, dirs, files in os.walk(local_path):
                    relative_path = os.path.relpath(root, local_path)
                    current_ftp_dir = os.path.join(ftp_dir, relative_path).replace("\\", "/")
                    self.ensure_ftp_directory(ftp, current_ftp_dir)

                    for file in files:
                        file_path = os.path.join(root, file)
                        ftp_file_path = os.path.join(current_ftp_dir, file).replace("\\", "/")
                        with open(file_path, "rb") as f:
                            ftp.storbinary(f"STOR {ftp_file_path}", f)
                            print(f"上传文件: {file_path} -> {ftp_file_path}")
            else:
                # 上传单个文件
                ftp_file_path = os.path.join(ftp_dir, ftp_basename).replace("\\", "/")
                with open(local_path, "rb") as f:
                    ftp.storbinary(f"STOR {ftp_file_path}", f)
                    print(f"上传文件: {local_path} -> {ftp_file_path}")

            ftp.quit()
        except Exception as e:
            print(f"上传失败: {local_path} -> {ftp_path}, 错误: {e}")
    
    def clean_ftp_path(self, path):
        """清理路径，去掉前缀，保留以 ftp:// 开头的部分"""
        if "ftp://" in path:
            return path[path.index("ftp://"):]
        return path

    def upload_single_folder(self, ftp_config, folder):
        """上传单个文件夹到 FTP"""
        config_path = os.path.join(folder, "config.json")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"文件夹 {folder} 中未找到 config.json")

        run_path = os.path.join(folder, "run.json")
        folder_name = os.path.basename(folder)
        if folder_name in self.folder_data:
            status_label = self.folder_data[folder_name]["status_label"]
        
        if not os.path.exists(run_path):
            if folder_name in self.folder_data:
                f_data = self.folder_data.get(folder_name)
                if f_data and "status_label" in f_data:  # 确保 status_label 存在
                    status_label = f_data["status_label"]
                    if status_label:  # 确保对象未被销毁
                        status_label = self.folder_data[folder_name]["status_label"]
                        wx.CallAfter(status_label.SetLabel, "文件上传中，请稍后...")
                        wx.CallAfter(status_label.SetForegroundColour, wx.Colour(0, 0, 255))  # 蓝色
                        wx.CallAfter(self.scroll_panel.Refresh)
                self.folder_data[folder_name]["status_txt"] = "文件上传中，请稍后..."
                self.folder_data[folder_name]["status_color"] = wx.Colour(0, 0, 255)

            # 读取 config.json 文件
            with open(config_path, 'r') as file:
                config = json.load(file)

            social_account = config.get("social_account", "default")
            if not social_account:
                raise ValueError("config.json 中缺少 social_account 字段！")

            # 收集需要上传的路径
            paths_to_upload = []

            # 遍历 videos 数组
            if "videos" in config:
                # 如果 widget 字段为 "GenTemplateImage"
                if config.get("widget") == "GenTemplateImage":
                    for raw_path in config["videos"]:
                        if raw_path:
                            # 清理路径
                            clean_path = self.clean_ftp_path(raw_path)
                            paths_to_upload.append(clean_path)
                else:
                    for video_entry in config.get("videos", []):
                        for key in ["video", "digital_human", "video2"]:
                            raw_path = video_entry.get(key)
                            if raw_path:
                                # 清理路径
                                clean_path = self.clean_ftp_path(raw_path)
                                paths_to_upload.append(clean_path)

            # 添加 use_video_subtitle 和 audio 路径
            if config.get("use_video_subtitle"):
                paths_to_upload.append(self.clean_ftp_path(config["use_video_subtitle"]))
            if config.get("audio"):
                paths_to_upload.append(config["audio"])

            max_file_threads = 3  # 每个任务内部的最大线程数
            with ThreadPoolExecutor(max_workers=max_file_threads) as file_executor:
                # 上传每个路径
                future_to_path = {}
                for path in paths_to_upload:
                    if not path.startswith("ftp://"):
                        continue

                    # 替换 {userid} 为 social_account
                    if "{userid}" in path:
                        path = path.replace("{userid}", social_account)

                    # 提取本地文件或目录名
                    local_name = os.path.basename(path.rstrip("/"))
                    local_path = os.path.join(folder, local_name)

                    if os.path.exists(local_path):
                        # self.upload_to_ftp(ftp_config, local_path, path)
                        future = file_executor.submit(self.upload_to_ftp, ftp_config, local_path, path)
                        future_to_path[future] = (local_path, path)
                
                for future in as_completed(future_to_path):
                    local_path, ftp_path = future_to_path[future]
                    try:
                        future.result()
                        print(f"上传完成: {local_path} -> {ftp_path}")
                    except Exception as e:
                        print(f"上传失败: {local_path} -> {ftp_path}, 错误: {e}")
            
            # 更新状态为上传完成
            if folder_name in self.folder_data:
                f_data = self.folder_data.get(folder_name)
                if f_data and "status_label" in f_data:  # 确保 status_label 存在
                    status_label = f_data["status_label"]
                    if status_label:  # 确保对象未被销毁
                        wx.CallAfter(status_label.SetLabel, "上传完成,准备执行模版...")
                        wx.CallAfter(status_label.SetForegroundColour, wx.Colour(255, 255, 0))  # 黄色
                        wx.CallAfter(self.scroll_panel.Refresh)
                self.folder_data[folder_name]["status_txt"] = "上传完成,准备执行模版..."
                self.folder_data[folder_name]["status_color"] = wx.Colour(255, 255, 0)
        
            # 将 config 转换为 JSON 文本
            config_text = json.dumps(config, ensure_ascii=False, indent=4)

            # 拼装任务数据
            data = {
                "ftp_folder_name": config.get("ftp_folder_name", ""),
                "social_account": config.get("social_account", ""),
                "config": config_text,  # 整个配置文件
                "use_anonymous": config.get("use_anonymous", False),
                "is_new_template": config.get("is_new_template", False),
                "matrix_template": config.get("matrix_template", ""),
                "publish_time": config.get("publish_time", ""),
                "music_name": config.get("music_name", ""),
                "music_index": config.get("music_index", ""),
                "music_volume": config.get("music_volume", 0.0),
                "original_volume": config.get("original_volume", 1.0),
                "window_product": config.get("window_product", ""),
                "tiktok_title": config.get("tiktok_title", ""),
                "tiktok_tags": config.get("tiktok_tags", ""),
                "tiktok_at": config.get("tiktok_at", ""),
                "first_comment": config.get("first_comment", ""),
                "repost_high_views": config.get("repost_high_views", False),
                "repost_views_threshold": config.get("repost_views_threshold", ""),
                "is_create_human": config.get("is_create_human", False),
                "widget": config.get("widget", "GenVideo_Template2")
            }

            # 调用 appendTask 方法提交任务数据
            sf_intent = FeiShuDoc()

            # 更新状态为“任务提交成功”
            try:
                if folder_name in self.folder_data:
                    f_data = self.folder_data.get(folder_name)
                    if f_data and "status_label" in f_data:  # 确保 status_label 存在
                        status_label = f_data["status_label"]
                        if status_label:  # 确保对象未被销毁
                            wx.CallAfter(status_label.SetLabel, "上传完成,准备执行模版...")
                            wx.CallAfter(status_label.SetForegroundColour, wx.Colour(255, 255, 0))  # 黄色
                            wx.CallAfter(self.scroll_panel.Refresh)
                    self.folder_data[folder_name]["status_txt"] = "上传完成,准备执行模版..."
                    self.folder_data[folder_name]["status_color"] = wx.Colour(255, 255, 0)
            except Exception as e:
                print(f"status_label.SetLabel 上传完成,准备执行模版...")
            
            record_id = sf_intent.appendTask(data)
        
        tips = "模版执行中..."
        color = wx.Colour(255, 255, 0)
        status = False
        create_human_status = False

        if os.path.exists(run_path):
            # 直接调用 repostTask, 重置任务
            sf_intent = FeiShuDoc()
            with open(run_path, "r", encoding="utf-8") as run_file:
                run_data = json.load(run_file)
                if run_data.get("status") == "error":
                    status = True
                if run_data.get("create_human_status") == "error":
                    create_human_status = True
                    tips = "模版已生成,可拉取资源(数字人生成中...)"
                    color = wx.Colour(0, 255, 0)
                
                # 更新状态为“任务提交成功”
                try:
                    if folder_name in self.folder_data:
                        data = self.folder_data.get(folder_name)
                        if data and "status_label" in data:  # 确保 status_label 存在
                            status_label = data["status_label"]
                            if status_label:  # 确保对象未被销毁
                                wx.CallAfter(status_label.SetLabel, tips)
                                wx.CallAfter(status_label.SetForegroundColour, color)  # 黄色或绿色
                                wx.CallAfter(self.scroll_panel.Refresh)
                        self.folder_data[folder_name]["status_txt"] = tips
                        self.folder_data[folder_name]["status_color"] = color
                except Exception as e:
                    print(f"status_label.SetLabel 模版执行中...")

                record_id = sf_intent.repostTask(run_data.get("record_id"), status, create_human_status)

        # 更新状态为“任务提交成功”
        try:
            if folder_name in self.folder_data:
                data = self.folder_data.get(folder_name)
                if data and "status_label" in data:  # 确保 status_label 存在
                    status_label = data["status_label"]
                    if status_label:  # 确保对象未被销毁
                        wx.CallAfter(status_label.SetLabel, tips)
                        wx.CallAfter(status_label.SetForegroundColour, color)  # 黄色或绿色
                        wx.CallAfter(self.scroll_panel.Refresh)
                self.folder_data[folder_name]["status_txt"] = tips
                self.folder_data[folder_name]["status_color"] = color
        except Exception as e:
            print(f"status_label.SetLabel 模版执行中...")
        
        # 创建 run.json 文件
        run_path = os.path.join(folder, "run.json")
        try:
            with open(run_path, 'w') as run_file:
                if create_human_status == True:
                    json.dump({"status": "downloadable", "create_human_status": "executing", "record_id": record_id}, run_file, ensure_ascii=False, indent=4)
                else:
                    json.dump({"status": "executing", "record_id": record_id}, run_file, ensure_ascii=False, indent=4)
            print(f"创建运行文件: {run_path}")
        except Exception as e:
            print(f"创建运行文件失败: {run_path}, 错误: {e}")
        
        self.folder_data[folder_name]["status_txt"] = ""

    def upload_directory_to_ftp(self, ftp_config, local_dir, ftp_dir, social_account):
        """
        将本地目录上传到 FTP 的指定路径。
        
        :param ftp_config: FTP 配置字典
        :param local_dir: 本地目录路径
        :param ftp_dir: FTP 目标目录路径
        """
        try:
            ftp = FTP()
            ftp.connect(ftp_config["host"], ftp_config["port"])
            ftp.login(ftp_config["username"], ftp_config["password"])

            # 替换路径中的 {userid} 为 social_account
            if "{userid}" in ftp_dir:
                ftp_dir = ftp_dir.replace("{userid}", social_account)

            # 确保目标 FTP 目录存在
            self.ensure_ftp_directory(ftp, ftp_dir)

            # 遍历本地目录并上传
            for root, dirs, files in os.walk(local_dir):
                # 计算相对路径并生成对应的 FTP 路径
                relative_path = os.path.relpath(root, local_dir)
                current_ftp_dir = os.path.join(ftp_dir, relative_path).replace("\\", "/")
                self.ensure_ftp_directory(ftp, current_ftp_dir)

                # 上传文件
                for file in files:
                    local_file_path = os.path.join(root, file)
                    ftp_file_path = os.path.join(current_ftp_dir, file).replace("\\", "/")
                    with open(local_file_path, "rb") as f:
                        ftp.storbinary(f"STOR {ftp_file_path}", f)
                        print(f"文件 {local_file_path} 已上传到 {ftp_file_path}")

            ftp.quit()
        except Exception as e:
            raise RuntimeError(f"FTP 上传失败：{e}")

    def ensure_ftp_directory(self, ftp, ftp_path):
        """
        确保 FTP 目录存在，如果不存在则递归创建。
        
        :param ftp: FTP 客户端对象
        :param ftp_path: FTP 路径
        """
        dirs = ftp_path.strip("/").split("/")
        for i in range(1, len(dirs) + 1):
            current_path = "/" + "/".join(dirs[:i])
            try:
                ftp.mkd(current_path)
            except Exception:
                # 忽略目录已存在的错误
                pass

    def upload_directory(self, ftp, local_dir, ftp_dir):
        """递归上传文件夹到 FTP"""
        for root, dirs, files in os.walk(local_dir):
            relative_path = os.path.relpath(root, local_dir)
            ftp_path = os.path.join(ftp_dir, relative_path).replace("\\", "/")
            self.ensure_ftp_directory(ftp, ftp_path)

            for file in files:
                local_file_path = os.path.join(root, file)
                ftp_file_path = os.path.join(ftp_path, file).replace("\\", "/")
                with open(local_file_path, "rb") as file:
                    ftp.storbinary(f"STOR {ftp_file_path}", file)
                    print(f"文件 {local_file_path} 已上传到 {ftp_file_path}")

    def open_folder(self, event, subfolder_name):
        """打开目标文件夹"""
        target_folder = os.path.join(self.folder_picker.GetPath(), subfolder_name)
        if not os.path.exists(target_folder):
            wx.MessageBox(f"文件夹 {target_folder} 不存在！", "错误", wx.OK | wx.ICON_ERROR)
            return

        # 根据操作系统打开文件夹
        try:
            if platform.system() == "Windows":
                os.startfile(target_folder)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", target_folder])
            else:  # Linux
                subprocess.Popen(["xdg-open", target_folder])
        except Exception as e:
            wx.MessageBox(f"无法打开文件夹: {e}", "错误", wx.OK | wx.ICON_ERROR)

    def show_template_settings(self, event, subfolder_name):
        folder_path = os.path.join(self.folder_picker.GetPath(), subfolder_name)
        music_path = self.find_longest_audio_file(folder_path)
        # 打开音频打点窗口
        marker_frame = MainFrame(self, music_path, folder_path)
        marker_frame.Show()


    def show_advanced_settings(self, event, subfolder_name):
        """显示高级设置浮窗"""
        folder_path = os.path.join(self.folder_picker.GetPath(), subfolder_name)
        config_path = os.path.join(folder_path, "config.json")
        dialog = AdvancedSettingsDialog(self, config_path)
        dialog.ShowModal()
        dialog.Destroy()
    
    def find_longest_audio_file(self, folder_path, audio_extensions=None):
        """
        查找指定文件夹中名称最长的音频文件路径。
        
        :param folder_path: 要搜索的文件夹路径
        :param audio_extensions: 音频文件扩展名列表，默认为常见的扩展名
        :return: 名称最长的音频文件路径（如果存在），否则为 None
        """
        if audio_extensions is None:
            audio_extensions = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"}
        
        longest_file_path = None
        max_name_length = 0

        # 遍历文件夹中的所有文件
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 检查文件是否为指定音频扩展名
                if any(file.lower().endswith(ext) for ext in audio_extensions):
                    # 获取完整路径和名称长度
                    full_path = os.path.join(root, file)
                    name_length = len(file)
                    
                    # 更新最长名称的文件
                    if name_length > max_name_length:
                        max_name_length = name_length
                        longest_file_path = full_path
        
        return longest_file_path

# 运行应用
if __name__ == "__main__":
    app = wx.App(False)
    frame = FolderListApp()
    app.MainLoop()