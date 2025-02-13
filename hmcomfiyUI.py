import wx
import json
import os
import random
import string
import uuid
import re
import ftplib
import time
import concurrent.futures
import wx.lib.scrolledpanel as scrolled
from maskEditor import MaskEditorFrame
from ryry import server_func
import threading
import cv2
import ffmpeg  # 需要先pip安装 ffmpeg-python 或用subprocess调ffmpeg命令
from pathlib import Path

class BusyDialog(wx.Dialog):
    def __init__(self, parent, message="请稍后..."):
        super().__init__(
            parent, title="", 
            style=wx.STAY_ON_TOP | wx.NO_BORDER  # 置顶 & 无边框
        )

        # 禁用父窗口交互
        if parent:
            parent.Enable(False)

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 在文字上下添加弹性空间，使其垂直居中
        sizer.AddStretchSpacer(1)
        label = wx.StaticText(
            panel, 
            label=message, 
            size=(300, -1),  # 给定更大宽度
            style=wx.ALIGN_CENTER
        )
        sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 30)
        sizer.AddStretchSpacer(1)

        panel.SetSizer(sizer)

        self.SetMinSize((320, 180))   # 确保对话框整体不太小
        self.Fit()
        self.CenterOnParent()

    def close_busy(self):
        """关闭此对话框，且恢复父窗口可交互。"""
        parent = self.GetParent()
        if parent:
            parent.Enable(True)
        self.Destroy()

class HMGenerateFrame(wx.Frame):
    def __init__(self, parent, folder_path):
        super().__init__(parent, title="数字人生成（多任务）", size=(1100, 750))
        self.parent = parent
        self.folder_path = folder_path

        # 1) 本次窗口的随机码，如 "res_A1b2C"
        self.res_random_code, self.time_stamp = self.generate_random_code()
        # 2) workflows 文件夹 & 文件列表
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.workflows_dir = os.path.join(base_dir, "hm_workflows")
        self.workflow_files = [f for f in os.listdir(self.workflows_dir) if f.endswith(".json")]

        # 3) 主面板 & 滚动区
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # -- 滚动面板，用于容纳多个 task
        self.scrolled_panel = scrolled.ScrolledPanel(panel, style=wx.VSCROLL)
        self.scrolled_panel.SetAutoLayout(1)
        self.scrolled_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        self.scrolled_sizer = wx.BoxSizer(wx.VERTICAL)
        self.scrolled_panel.SetSizer(self.scrolled_sizer)

        # 4) 底部按钮：添加 & 执行次数 & 提交 & 取消
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # (A) “添加任务”按钮
        self.add_button = wx.Button(panel, label="添加任务")
        btn_sizer.Add(self.add_button, 0, wx.ALL, 5)

        # (B) 弹性空间，让后续控件靠右
        btn_sizer.AddStretchSpacer()

        # (C) “执行次数”与其输入框
        repeat_label = wx.StaticText(panel, label="执行次数:")
        self.repeat_ctrl = wx.TextCtrl(panel, value="1", size=(50, -1))
        btn_sizer.Add(repeat_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        btn_sizer.Add(self.repeat_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # (D) “确定” & “取消”按钮
        self.ok_button = wx.Button(panel, label="确定")
        self.cancel_button = wx.Button(panel, label="取消")
        btn_sizer.Add(self.ok_button, 0, wx.ALL, 5)
        btn_sizer.Add(self.cancel_button, 0, wx.ALL, 5)

        # 主布局
        main_sizer.Add(self.scrolled_panel, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(main_sizer)

        # 事件绑定
        self.add_button.Bind(wx.EVT_BUTTON, self.on_add_task)
        self.ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)

        # 存放所有任务面板
        self.task_panels = []

        # 首次打开时先自动添加一个任务
        self.on_add_task(None)

        self.CentreOnParent()

    def generate_random_code(self, length=5):
        """生成 res_ + length 位随机字符串，如 'res_Ab3Kp'"""
        suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        return f"res_{suffix}", time.strftime("%Y%m%d_%H%M%S")

    def on_add_task(self, event):
        prev_flow_output = f"aigc_output/{self.res_random_code}_{self.time_stamp}"
        prev_local_path = os.path.join(self.folder_path, "reslib", self.res_random_code)

        prev_workflow_name = None
        prev_text_controls = {}
        prev_upload_paths = {}

        if self.task_panels:
            last_panel = self.task_panels[-1]
            prev_flow_output = last_panel.flow_output_ctrl.GetValue()
            prev_local_path = last_panel.local_path_ctrl.GetValue()
            prev_workflow_name = last_panel.get_current_workflow_name()
            # prev_text_controls = last_panel.get_all_text_controls()
            # prev_upload_paths = last_panel.get_all_upload_paths()

        new_panel = TaskPanel(
            parent=self.scrolled_panel,
            workflow_dir=self.workflows_dir,
            workflow_files=self.workflow_files,
            default_flow_output=prev_flow_output,
            default_local_path=prev_local_path
        )

        self.task_panels.append(new_panel)

        # 如果有 workflow_name，就先加载它
        if prev_workflow_name:
            # 先手动选中
            new_panel.select_workflow(prev_workflow_name)
            # 再 load
            new_panel.load_workflow(prev_workflow_name)
            new_panel.set_all_text_controls(prev_text_controls)
            new_panel.set_all_upload_paths(prev_upload_paths)

        # 用 staticboxsizer 包围
        box = wx.StaticBox(self.scrolled_panel, label=f"任务 {len(self.task_panels)}")
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        box_sizer.Add(new_panel, 1, wx.EXPAND | wx.ALL, 5)

        self.scrolled_sizer.Add(box_sizer, 0, wx.EXPAND | wx.ALL, 5)
        self.scrolled_panel.Layout()
        self.scrolled_panel.SetupScrolling()

        # 让布局先完成再滚动到底部
        def scroll_to_bottom():
            scroll_range = self.scrolled_panel.GetScrollRange(wx.VERTICAL)
            self.scrolled_panel.Scroll(0, scroll_range)

        wx.CallAfter(scroll_to_bottom)

    def on_ok(self, event):
        """
        当用户点击“确定”时：
        1) 显示 BusyDialog
        2) 启动子线程 do_submit_in_thread
        """
        # 显示忙碌提示
        self.busy_info = BusyDialog(self, "提交中，请稍后...")
        self.busy_info.Show()
        wx.GetApp().Yield()  # 刷新界面，显示BusyDialog

        # 启动子线程执行 do_submit_in_thread
        self.worker_thread = threading.Thread(target=self.do_submit_in_thread)
        self.worker_thread.start()

    def do_submit_in_thread(self):
        """
        在子线程执行真正的耗时操作:
        - repeat_count
        - 收集 flows
        - FTP 并发上传
        - 调 server_func.AsyncTask
        - save_req_json
        完成后用 wx.CallAfter(...) 通知主线程
        """
        try:
            repeat_count = int(self.repeat_ctrl.GetValue())
        except ValueError as e:
            # 通知主线程报错
            wx.CallAfter(self.on_submit_done, False, f"执行次数必须是数字！: {e}")
            return
        
        try:
            # 1) 收集多任务 flows
            flows = []
            cmd_titles = []  # 用于保存所有任务名
            
            for panel in self.task_panels:
                data = panel.get_task_data()
                flows.append(data)

            single_submission = {
                "taskuuid": str(uuid.uuid4())[:8],
                "flows": flows
            }

            # 提取每个 flow_api 的任务名，并加入 cmd_titles 列表
            for flow in flows:
                flow_api = flow.get("flow_api", "")
                if flow_api:
                    # 提取 "xxxx/aaaa/test/任务名.json" 中的 "任务名"
                    task_name = flow_api.split('/')[-1].split('.')[0]
                    if task_name == "DreamFace_Workflow":
                        cmd_titles.append("数字人生成")
                    else:
                        cmd_titles.append(task_name)

            # 拼接所有任务名，使用 "-" 连接
            cmd_title = "-".join(cmd_titles)

            # 2) FTP并发上传 + 替换
            updated_submission = self.upload_all_to_ftp(single_submission)
            # === 在这里调用“扁平化”处理 ===
            self.flatten_flow_inputs(updated_submission)
            updated_submission["cmd_title"] = cmd_title

            for _ in range(repeat_count):
                # 3) 调 server_func.AsyncTask
                api = server_func.AsyncTask("DreamFace_Workflow", single_submission)
                taskuuid = api.call()
                updated_submission["taskuuid"] = taskuuid
                # 4) 保存到一个新的 req_XXXXX.json
                self.save_req_json(updated_submission)

            # 全部成功 => 通知主线程 success
            wx.CallAfter(self.on_submit_done, True, None)
        except Exception as e:
            # 出现异常 => 通知主线程 failure
            wx.CallAfter(self.on_submit_done, False, f"提交失败: {e}")
    
    def parse_str_to_val(self, s: str):
        """
        尝试将字符串 s 转为数字或布尔：
        - "True"  -> True
        - "False" -> False
        - "123"   -> int(123)
        - "12.5"  -> float(12.5)
        - 其他情况 -> 保持原字符串
        """
        if s == "True":
            return True
        if s == "False":
            return False

        # 先试 int
        try:
            return int(s)
        except ValueError:
            pass

        # 再试 float
        try:
            return float(s)
        except ValueError:
            pass

        # 都不行就原样返回
        return s
    
    def ftp_file_to_folder(self, path_str: str) -> str:
        """
        如果 path_str 形如:
        ftp://183.6.90.205:2221/mnt/NAS/mcn/reslib/20250208_181425_8j30wSl2/WX20250124-160928@2x.png
        那么把它截断到上一级目录，并在末尾加 '/', 变成:
        ftp://183.6.90.205:2221/mnt/NAS/mcn/reslib/20250208_181425_8j30wSl2/

        否则原样返回。
        """
        if path_str.startswith("ftp://") and not path_str.endswith("/"):
            # path_str 里去掉 "ftp://" 再看剩下的部分
            # 例如 "183.6.90.205:2221/mnt/NAS/mcn/reslib/20250208_xxx/filename.png"
            without_prefix = path_str[len("ftp://"):]
            # 如果只要简单判断“不是以 / 结尾就认为是文件”，可以直接拆分:
            # rsplit('/', 1) 从右边只分割一次
            parts = without_prefix.rsplit('/', 1)
            if len(parts) == 2:
                # parts[0] = "183.6.90.205:2221/mnt/NAS/mcn/reslib/20250208_xxx"
                # parts[1] = "filename.png"
                # 可以再看一下 parts[1] 是否含 '.' 来初步判断是否真的像个文件
                # 如果要更宽松判断，“只要不是空就说明是文件名”也行
                if '.' in parts[1]:
                    # 认为是文件
                    folder_only = parts[0] + '/'  # 变回末尾带 '/'
                    return "ftp://" + folder_only
        # 其他情况原样返回
        return path_str

    def flatten_flow_inputs(self, submission: dict):
        for flow in submission["flows"]:
            flow_inputs = flow.get("flow_inputs", {})
            new_flow_inputs = {}

            for key, sub_dict in flow_inputs.items():
                # sub_dict 可能是 {"text": "xxx"} 或 {"image": "..."} 等
                if "text" in sub_dict:
                    raw_val = sub_dict["text"]
                    new_flow_inputs[key] = self.parse_str_to_val(raw_val)
                elif "image" in sub_dict:
                    # 先取到原字符串
                    ftp_path = sub_dict["image"]
                    # 如果是 ftp 并结尾带文件，则转成上一级目录
                    # ftp_path = self.ftp_file_to_folder(ftp_path)
                    new_flow_inputs[key] = ftp_path
                elif "video" in sub_dict:
                    ftp_path = sub_dict["video"]
                    # ftp_path = self.ftp_file_to_folder(ftp_path)
                    new_flow_inputs[key] = ftp_path
                else:
                    new_flow_inputs[key] = sub_dict

            # 替换
            flow["flow_inputs"] = new_flow_inputs
    
    def on_submit_done(self, success, error_msg):
        """
        回到主线程，关闭 BusyInfo 并关闭窗口或提示错误
        """
        # 关闭 busy_info
        if hasattr(self, 'busy_info') and self.busy_info:
            self.busy_info.close_busy()
            del self.busy_info

        if success:
            # 成功 => 关闭窗口
            self.Close()
        else:
            # 失败 => 弹框提示
            wx.MessageBox(error_msg, "错误", wx.OK | wx.ICON_ERROR)

    def upload_all_to_ftp(self, submission):
        ftp_reslib_base = "ftp://183.6.90.205:2221/mnt/NAS/mcn/reslib"
        local_to_ftp = {}

        time_stamp = time.strftime("%Y%m%d_%H%M%S")
        random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        ftp_reslib_dir = f"{ftp_reslib_base}/{time_stamp}_{random_str}"

        for flow in submission["flows"]:
            flow_inputs = flow.get("flow_inputs", {})
            for node_id, node_data in flow_inputs.items():
                # ---------- 处理 image ----------
                if "image" in node_data:
                    image_data = node_data["image"]
                    if isinstance(image_data, str):
                        # 单文件
                        if os.path.isfile(image_data):
                            base = os.path.basename(image_data)
                            ftp_path = f"{ftp_reslib_dir}/{base}"
                            local_to_ftp[image_data] = ftp_path
                    elif isinstance(image_data, list):
                        # 多文件（文件夹内收集来的）
                        for local_path in image_data:
                            if os.path.isfile(local_path):
                                base = os.path.basename(local_path)
                                ftp_path = f"{ftp_reslib_dir}/{base}"
                                local_to_ftp[local_path] = ftp_path

                # ---------- 处理 video ----------
                if "video" in node_data:
                    local_vid_path = node_data["video"]
                    if local_vid_path and os.path.isfile(local_vid_path):
                        base_vid = os.path.basename(local_vid_path)
                        ftp_vid_path = f"{ftp_reslib_dir}/{base_vid}"
                        local_to_ftp[local_vid_path] = ftp_vid_path

        # (有要上传的文件) => 并发上传
        if local_to_ftp:
            self.ftp_upload_concurrent(local_to_ftp)

        # **替换 submission 里的本地路径 => FTP 路径**
        for flow in submission["flows"]:
            flow_inputs = flow.get("flow_inputs", {})
            for node_id, node_data in flow_inputs.items():
                # ---- 替换 image ----
                if "image" in node_data:
                    image_data = node_data["image"]
                    if isinstance(image_data, str):
                        # 单文件 => 直接替换
                        if image_data in local_to_ftp:
                            node_data["image"] = local_to_ftp[image_data]
                    elif isinstance(image_data, list):
                        # 多文件 => 逐个替换，然后只取第一个
                        new_list = []
                        for local_path in image_data:
                            if local_path in local_to_ftp:
                                new_list.append(local_to_ftp[local_path])
                            else:
                                new_list.append(local_path)
                        # 如果有多条，只保留第一条
                        if new_list:
                            node_data["image"] = new_list[0]
                        else:
                            node_data["image"] = ""  # or None, 自行决定

                # ---- 替换 video ----
                if "video" in node_data:
                    local_vid_path = node_data["video"]
                    if local_vid_path in local_to_ftp:
                        node_data["video"] = local_to_ftp[local_vid_path]

        return submission
    
    def ftp_upload_concurrent(self, local_to_ftp):
        """
        用5线程并发上传 local_path => ftp_path
        ftp: 183.6.90.205:2221, user=mcn, pass=meco@2024+
        需要在 FTP 端先确保 workflows/reslib 目录可写。
        """
        max_workers = 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {}
            for local_path, ftp_path in local_to_ftp.items():
                future = executor.submit(self.upload_single_file, local_path, ftp_path)
                future_to_file[future] = (local_path, ftp_path)

            # 等待任务完成
            for future in concurrent.futures.as_completed(future_to_file):
                local_path, ftp_path = future_to_file[future]
                try:
                    future.result()
                    print(f"上传成功: {local_path} -> {ftp_path}")
                except Exception as exc:
                    print(f"上传失败: {local_path} => {ftp_path}, 错误: {exc}")

    def upload_single_file(self, local_path, ftp_path):
        """
        上传单个文件:
        ftp://183.6.90.205:2221/mnt/NAS/mcn/workflows/xxx.json
        or
        ftp://183.6.90.205:2221/mnt/NAS/mcn/reslib/xxx/xxx.png
        """
        # 解析 ftp_path => relative path
        # ftp_path 形如: ftp://183.6.90.205:2221/mnt/NAS/mcn/workflows/xxx.json
        # real ftp dir => /mnt/NAS/mcn/workflows
        # real ftp file => /mnt/NAS/mcn/workflows/xxx.json
        # we can parse out the path after "ftp://183.6.90.205:2221"
        prefix = "ftp://183.6.90.205:2221"
        if not ftp_path.startswith(prefix):
            raise ValueError(f"ftp_path 不合法: {ftp_path}")

        relative_path = ftp_path[len(prefix):]  # => /mnt/NAS/mcn/workflows/xxx.json
        remote_dir = os.path.dirname(relative_path)
        remote_file = os.path.basename(relative_path)

        # 连接 FTP
        ftp_host = "183.6.90.205"
        ftp_port = 2221
        ftp_user = "mcn"
        ftp_pass = "meco@2024+"

        with ftplib.FTP() as ftp:
            ftp.connect(ftp_host, ftp_port, timeout=30)
            ftp.login(ftp_user, ftp_pass)

            # 确保 remote_dir 存在
            self.ftp_makedirs(ftp, remote_dir)

            # 切换目录
            ftp.cwd(remote_dir)
            # 上传
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_file}", f)
            ftp.quit()

    def ftp_makedirs(self, ftp, remote_dir):
        """
        递归创建 FTP 目录
        remote_dir 形如: /mnt/NAS/mcn/reslib/20230614_xxxx
        """
        if not remote_dir.startswith("/"):
            remote_dir = "/" + remote_dir
        parts = remote_dir.split("/")
        path = ""
        for p in parts:
            if not p:  # split后可能有空
                continue
            path += f"/{p}"
            try:
                ftp.mkd(path)
            except Exception:
                # 可能已存在
                pass

    def on_cancel(self, event):
        self.Close()
    
    def Destroy(self):
        # 1) 自定义逻辑
        if hasattr(self.parent, "timer"):
            self.parent.timer.Start(10000)  # 每10秒刷新一次，或你原先的间隔
        
        # 2) 调用父类Destroy，否则不会真正释放资源
        return super().Destroy()

    def save_req_json(self, submission):
        """
        每次提交，都在 reslib/ 下创建一个单独文件: req_XXXXX.json
        """
        reslib_dir = os.path.join(self.folder_path, "reslib")
        if not os.path.exists(reslib_dir):
            os.makedirs(reslib_dir, exist_ok=True)

        # 生成 5 位随机码
        # suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        suffix = self.res_random_code
        filename = f"{suffix}.json"

        req_path = os.path.join(reslib_dir, filename)
        # 直接写 submission
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(submission, f, ensure_ascii=False, indent=4)

        print(f"已创建 {req_path}，内容 => {submission}")


class MyImageDropTarget(wx.FileDropTarget):
    """
    自定义文件拖放目标，用于接收图片文件拖入到静态位图中。
    """
    def __init__(self, parent_panel, node_id, preview_bitmap, on_image_selected):
        super().__init__()
        self.parent_panel = parent_panel
        self.node_id = node_id
        self.preview_bitmap = preview_bitmap
        self.on_image_selected = on_image_selected

    def OnDropFiles(self, x, y, filenames):
        if not filenames:
            return False
        local_path = filenames[0]
        
        # Distinguish folder vs file
        if os.path.isdir(local_path):
            # 让 parent_panel处理
            self.on_image_selected(self.node_id, self.preview_bitmap, local_path, is_folder=True)
        else:
            self.on_image_selected(self.node_id, self.preview_bitmap, local_path, is_folder=False)
        return True

class TaskPanel(wx.Panel):
    """每个TaskPanel对应一个任务."""
    def __init__(self, parent, workflow_dir, workflow_files, default_flow_output, default_local_path):
        super().__init__(parent)
        self.workflow_dir = workflow_dir
        self.workflow_files = workflow_files

        self.workflow_data = None
        # 保留 text_controls，用于记录 "text", "seed", "steps", "cfg", "denoise" ...
        self.text_controls = {}
        # 新增：upload_paths，用于记录 node_id -> local_image_path
        self.upload_paths = {}

        self.preview_bitmaps = {}

        self.flow_output_ctrl = None
        self.local_path_ctrl = None

         # ### 新增：用于保存 node_id -> image_path文本框控件 ###
        self.image_path_ctrl = {}

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 1) workflow choice
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(wx.StaticText(self, label="Workflow:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.workflow_choice = wx.Choice(self, choices=self.workflow_files)
        if self.workflow_files:
            self.workflow_choice.SetSelection(0)
        hbox.Add(self.workflow_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.workflow_choice.Bind(wx.EVT_CHOICE, self.on_workflow_select)
        main_sizer.Add(hbox, 0, wx.EXPAND | wx.ALL, 5)

        # 2) 参数输入区域：text_inputs_sizer
        self.text_inputs_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.text_inputs_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # 3) flow_output & local_path
        fl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        fl_sizer.Add(wx.StaticText(self, label="flow_output:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.flow_output_ctrl = wx.TextCtrl(self, value=default_flow_output, size=(300, -1))
        fl_sizer.Add(self.flow_output_ctrl, 1, wx.ALL | wx.EXPAND, 5)

        fl_sizer.Add(wx.StaticText(self, label="local_path:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.local_path_ctrl = wx.TextCtrl(self, value=default_local_path, size=(300, -1))
        fl_sizer.Add(self.local_path_ctrl, 1, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(fl_sizer, 0, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(main_sizer)

        # 如果 workflow_files 非空，默认载入第一个
        if self.workflow_files:
            self.load_workflow(self.workflow_files[0])

    def select_workflow(self, workflow_name):
        """
        根据 workflow_name 找到它在 self.workflow_files 中的 index，
        并 self.workflow_choice.SetSelection(index)
        """
        if workflow_name in self.workflow_files:
            idx = self.workflow_files.index(workflow_name)
            self.workflow_choice.SetSelection(idx)
        else:
            # 找不到就不动
            pass
    
    def get_current_workflow_name(self):
        """返回当前选择的 workflow 文件名"""
        return self.workflow_choice.GetStringSelection()

    def get_all_text_controls(self):
        """
        返回 { node_id: { field_name: 字符串值 } }
        """
        result = {}
        for node_id, fields_dict in self.text_controls.items():
            result[node_id] = {}
            for field_name, ctrl in fields_dict.items():
                if isinstance(ctrl, wx.TextCtrl):
                    result[node_id][field_name] = ctrl.GetValue()
                elif isinstance(ctrl, wx.Choice):
                    result[node_id][field_name] = ctrl.GetStringSelection()
                else:
                    # 其他控件类型, 看情况处理
                    result[node_id][field_name] = ""
        return result

    def get_all_upload_paths(self):
        """返回self.upload_paths的深拷贝，也可直接返回dict"""
        return dict(self.upload_paths)

    def set_all_text_controls(self, text_data):
        """
        根据 text_data 设置当前面板的 text_controls
        text_data 格式: {
            node_id: {
                field_name: val
            }
        }
        """
        for node_id, fields in text_data.items():
            # 如果当前面板中没有这个 node_id，就跳过
            if node_id not in self.text_controls:
                continue

            for field_name, val in fields.items():
                if field_name not in self.text_controls[node_id]:
                    continue

                ctrl = self.text_controls[node_id][field_name]

                if isinstance(ctrl, wx.TextCtrl):
                    # TextCtrl => 用 SetValue
                    ctrl.SetValue(str(val))
                elif isinstance(ctrl, wx.Choice):
                    # Choice => 用 SetStringSelection 或 SetSelection
                    # 先尝试直接 SetStringSelection，如果选项在 Choice 中，可以成功
                    # 否则就默认选第0个
                    if ctrl.FindString(str(val)) != wx.NOT_FOUND:
                        ctrl.SetStringSelection(str(val))
                    else:
                        ctrl.SetSelection(0)
                else:
                    # 其他控件类型，视需求处理
                    pass

        self.text_inputs_sizer.Layout()
        self.Layout()

    def set_all_upload_paths(self, upload_data):
        """
        upload_data: { node_id: local_image_path }
        """
        for node_id, local_path in upload_data.items():
            self.upload_paths[node_id] = local_path
            # 如果已经创建 preview_bitmaps[node_id]，更新预览
            if node_id in self.preview_bitmaps:
                self.update_preview_bitmap(node_id, local_path)

            # ### 新增：若存在 image_path_ctrl[node_id]，也同步显示 ###
            if node_id in self.image_path_ctrl:
                self.image_path_ctrl[node_id].SetValue(local_path)
    
    def update_preview_bitmap(self, node_id, local_path):
        if not os.path.exists(local_path):
            return
        
        bmp_ctrl = self.preview_bitmaps[node_id]  # preview_bitmap
        w, h = bmp_ctrl.GetSize()

        img = wx.Image(local_path, wx.BITMAP_TYPE_ANY)
        orig_w, orig_h = img.GetWidth(), img.GetHeight()
        ratio = min(w/float(orig_w), h/float(orig_h))
        new_w = max(1, int(orig_w * ratio))
        new_h = max(1, int(orig_h * ratio))

        img = img.Scale(new_w, new_h, wx.IMAGE_QUALITY_HIGH)
        bmp_ctrl.SetBitmap(wx.Bitmap(img))

    def on_workflow_select(self, event):
        selection = self.workflow_choice.GetStringSelection()
        if not selection:
            return
        self.load_workflow(selection)

    def load_workflow(self, workflow_name):
        path = os.path.join(self.workflow_dir, workflow_name)
        if not os.path.exists(path):
            wx.MessageBox(f"找不到 {path}", "错误", wx.OK | wx.ICON_ERROR)
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                self.workflow_data = json.load(f)
        except Exception as e:
            wx.MessageBox(f"读取 workflow JSON 失败: {e}", "错误", wx.OK | wx.ICON_ERROR)
            return

        # 1) 清理旧控件
        self.text_inputs_sizer.Clear(delete_windows=True)
        self.text_controls.clear()
        self.upload_paths.clear()
        self.preview_bitmaps.clear()
        self.image_path_ctrl.clear()

        # 2) 新建四个列表: upload, textnormal, textspecial, others, blocks_model
        blocks_upload      = []
        blocks_textnormal  = []
        blocks_textspecial = []
        blocks_others      = []
        blocks_model       = []
        blocks_lora        = []

        # 关键字匹配(大小写/部分匹配):
        special_keywords = ["填充", "负向提示词", "CLIP文本编码"]

        base_dir = os.path.dirname(os.path.abspath(__file__))
        models_dir = os.path.join(base_dir, "models")

        # -- models 目录逻辑 (unet_name 用)
        model_files = []
        if os.path.isdir(models_dir):
            for f in os.listdir(models_dir):
                # 如果是以 '.' 开头，直接跳过
                if f.startswith("."):
                    continue
                full_path = os.path.join(models_dir, f)
                if os.path.isfile(full_path):
                    f_modified = f.replace(":", "/")
                    model_files.append(f_modified)
        if not model_files:
            model_files = ["(No Files Found in models folder)"]
        
        # -- loras 目录逻辑 (lora_name 用)
        loras_dir = os.path.join(base_dir, "loras")
        lora_files = []
        if os.path.isdir(loras_dir):
            for f in os.listdir(loras_dir):
                if f.startswith("."):
                    continue
                full_path = os.path.join(loras_dir, f)
                if os.path.isfile(full_path):
                    f_modified = f.replace(":", "/")
                    lora_files.append(f_modified)
        if not lora_files:
            lora_files = ["(No Files Found in loras folder)"]

        field_choices_map = {
            "unet_name": model_files,
            "lora_name": lora_files
        }

        for node_id, node_data in self.workflow_data.items():
            inputs = node_data.get("inputs", {})
            title = node_data.get("_meta", {}).get("title", f"Node {node_id}")

            # (A) 若 "upload"
            if "upload" in inputs:
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                label = wx.StaticText(self, label=f"{node_id} {title} (upload):")
                row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                # 预览面板 + bitmap
                bmp_panel = wx.Panel(self, size=(50, 50))
                bmp_panel.SetBackgroundColour(wx.Colour(60, 60, 60))
                bitmap_preview = wx.StaticBitmap(bmp_panel, size=(50, 50), pos=(0, 0))
                self.preview_bitmaps[node_id] = bitmap_preview

                row_sizer.Add(bmp_panel, 0, wx.ALL, 5)

                # 文本框(显示或编辑图片路径)
                image_path = wx.TextCtrl(self, value="", size=(400, -1))
                self.image_path_ctrl[node_id] = image_path
                row_sizer.Add(image_path, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                # “编辑遮罩”按钮
                # mask_button = wx.Button(self, label="编辑遮罩")
                # row_sizer.Add(mask_button, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                # mask_button.Bind(wx.EVT_BUTTON,
                #     lambda evt, nid=node_id: self.on_edit_mask(evt, nid))

                # 拖拽/点击
                drop_target = MyImageDropTarget(self, node_id, bitmap_preview, self.on_image_selected)
                bitmap_preview.SetDropTarget(drop_target)
                bitmap_preview.Bind(wx.EVT_LEFT_UP,
                    lambda evt, nid=node_id, bmp=bitmap_preview: self.on_select_image(evt, nid, bmp)
                )

                blocks_upload.append(row_sizer)
            
            # (A) 若 "upload"
            if "video" in inputs:
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                label = wx.StaticText(self, label=f"{node_id} {title} (video):")
                row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                # 预览面板 + bitmap
                bmp_panel = wx.Panel(self, size=(50, 50))
                bmp_panel.SetBackgroundColour(wx.Colour(60, 60, 60))
                bitmap_preview = wx.StaticBitmap(bmp_panel, size=(50, 50), pos=(0, 0))
                self.preview_bitmaps[node_id] = bitmap_preview

                row_sizer.Add(bmp_panel, 0, wx.ALL, 5)

                # 文本框(显示或编辑图片路径)
                image_path = wx.TextCtrl(self, value="", size=(400, -1))
                self.image_path_ctrl[node_id] = image_path
                row_sizer.Add(image_path, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                # 拖拽/点击
                drop_target = MyImageDropTarget(self, node_id, bitmap_preview, self.on_image_selected)
                bitmap_preview.SetDropTarget(drop_target)
                bitmap_preview.Bind(wx.EVT_LEFT_UP,
                    lambda evt, nid=node_id, bmp=bitmap_preview: self.on_select_image(evt, nid, bmp)
                )

                blocks_upload.append(row_sizer)

            # (B) 若 "text" 是字符串
            if "text" in inputs and isinstance(inputs["text"], str):
                default_text = inputs["text"]
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                label = wx.StaticText(self, label=f"{node_id} {title} (text):")
                text_ctrl = wx.TextCtrl(self, value=default_text, size=(400, -1))
                row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                row_sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 5)

                self.text_controls.setdefault(node_id, {})["text"] = text_ctrl

                # 检查 title 是否含特殊关键字
                # 先统一小写，看看是否含 "负向提示词" 或 "CLIP文本编码"
                title_lower = title.lower()
                found_special = False
                for kw in special_keywords:
                    if kw.lower() in title_lower:
                        found_special = True
                        break
                
                if found_special:
                    blocks_textspecial.append(row_sizer)
                else:
                    blocks_textnormal.append(row_sizer)
            
            if "prompt" in inputs and isinstance(inputs["prompt"], str):
                default_text = inputs["prompt"]
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                label = wx.StaticText(self, label=f"{node_id} {title} (prompt):")
                text_ctrl = wx.TextCtrl(self, value=default_text, size=(400, -1))
                row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                row_sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 5)

                self.text_controls.setdefault(node_id, {})["prompt"] = text_ctrl

                # 检查 title 是否含特殊关键字
                # 先统一小写，看看是否含 "负向提示词" 或 "CLIP文本编码"
                title_lower = title.lower()
                found_special = False
                for kw in special_keywords:
                    if kw.lower() in title_lower:
                        found_special = True
                        break
                
                if found_special:
                    blocks_textspecial.append(row_sizer)
                else:
                    blocks_textnormal.append(row_sizer)
            
            if "negative_prompt" in inputs and isinstance(inputs["negative_prompt"], str):
                default_text = inputs["negative_prompt"]
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                label = wx.StaticText(self, label=f"{node_id} {title} (negative_prompt):")
                text_ctrl = wx.TextCtrl(self, value=default_text, size=(400, -1))
                row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                row_sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 5)

                self.text_controls.setdefault(node_id, {})["negative_prompt"] = text_ctrl

                # 检查 title 是否含特殊关键字
                # 先统一小写，看看是否含 "负向提示词" 或 "CLIP文本编码"
                title_lower = title.lower()
                found_special = False
                for kw in special_keywords:
                    if kw.lower() in title_lower:
                        found_special = True
                        break
                
                if found_special:
                    blocks_textspecial.append(row_sizer)
                else:
                    blocks_textnormal.append(row_sizer)

            if "unet_name" in inputs:
                default_val = inputs["unet_name"]
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)
                label = wx.StaticText(self, label=f"{node_id} {title} (unet_name):")
                row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                # 创建下拉框
                choices = field_choices_map["unet_name"]  # 取到可选列表
                choice_ctrl = wx.Choice(self, choices=choices)

                # 如果 workflow.json 里原本的 default_val 在 choices 中，就选中它
                if default_val in choices:
                    choice_ctrl.SetSelection(choices.index(default_val))
                else:
                    choice_ctrl.SetSelection(0)  # 否则默认选第一个

                row_sizer.Add(choice_ctrl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                self.text_controls.setdefault(node_id, {})["unet_name"] = choice_ctrl
                
                blocks_model.append(row_sizer)
            
            if "lora_name" in inputs or "strength_model" in inputs:
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)

                # 如果包含 lora_name，就在这行里先加下拉框
                if "lora_name" in inputs:
                    default_val = inputs["lora_name"]
                    label_lora = wx.StaticText(self, label=f"{node_id} {title} (lora_name):")
                    row_sizer.Add(label_lora, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                    # 创建下拉框
                    choices = field_choices_map["lora_name"]  
                    choice_ctrl = wx.Choice(self, choices=choices, size=(200, -1))

                    # 如果 JSON 里有默认值且在 choices 中 => 选中
                    if default_val in choices:
                        choice_ctrl.SetSelection(choices.index(default_val))
                    else:
                        choice_ctrl.SetSelection(0)

                    row_sizer.Add(choice_ctrl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                    self.text_controls.setdefault(node_id, {})["lora_name"] = choice_ctrl

                # 如果包含 strength_model，就在同一行里继续加
                if "strength_model" in inputs:
                    default_val = inputs["strength_model"]
                    if not isinstance(default_val, (float, int)):
                        default_val = 0.5

                    label_strength = wx.StaticText(self, label=f"(strength_model 0~1):")
                    row_sizer.Add(label_strength, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                    strength_ctrl = wx.TextCtrl(self, value=str(default_val), size=(60, -1))
                    row_sizer.Add(strength_ctrl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                    self.text_controls.setdefault(node_id, {})["strength_model"] = strength_ctrl

                # 把这行添加到 blocks_lora
                blocks_lora.append(row_sizer)

            # 先把 seed/steps/cfg/denoise 合并处理：
            fields_for_one_line = ["seed", "steps", "cfg", "denoise"]
            found_any = False
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)

            first_field = True  # 用来标记是否是该行的第一个字段

            for field_name in fields_for_one_line:
                if field_name in inputs:
                    found_any = True
                    default_val = inputs[field_name]
                    # 如果是 list，就跳过
                    if isinstance(default_val, list):
                        continue
                    # seed 特殊: 如果是默认值，就改成 "random"
                    if field_name == "seed":
                        default_val = "random"

                    # 只有第一个字段才显示 node_id + title
                    if first_field:
                        label_text = f"{node_id} {title} ({field_name}):"
                        first_field = False
                    else:
                        # 后续字段只显示字段名
                        label_text = f"({field_name}):"

                    label = wx.StaticText(self, label=label_text)
                    row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                    
                    if field_name == "seed":
                        text_ctrl = wx.TextCtrl(self, value=str(default_val), size=(200, -1))
                    else:
                        text_ctrl = wx.TextCtrl(self, value=str(default_val), size=(60, -1))
                    row_sizer.Add(text_ctrl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                    # 存起来方便后面 get_task_data
                    self.text_controls.setdefault(node_id, {})[field_name] = text_ctrl
            if found_any:
                blocks_others.append(row_sizer)

        # 3) 按固定顺序插入 blocks: upload -> textnormal -> textspecial -> others -> model -> lora
        for sizer_item in blocks_upload:
            self.text_inputs_sizer.Add(sizer_item, 0, wx.EXPAND)

        for sizer_item in blocks_textnormal:
            self.text_inputs_sizer.Add(sizer_item, 0, wx.EXPAND)

        for sizer_item in blocks_textspecial:
            self.text_inputs_sizer.Add(sizer_item, 0, wx.EXPAND)

        for sizer_item in blocks_others:
            self.text_inputs_sizer.Add(sizer_item, 0, wx.EXPAND)
        
        for sizer_item in blocks_model:
            self.text_inputs_sizer.Add(sizer_item, 0, wx.EXPAND)
        
        for sizer_item in blocks_lora:
            self.text_inputs_sizer.Add(sizer_item, 0, wx.EXPAND)

        # 4) 布局
        self.text_inputs_sizer.Layout()
        self.Fit()
        self.Layout()

        parent_scrolled = self.GetParent()
        if isinstance(parent_scrolled, scrolled.ScrolledPanel):
            parent_scrolled.SetupScrolling(scroll_x=False, scroll_y=True)

    def on_edit_mask(self, event, node_id):
        """
        打开编辑遮罩窗口
        1) 获取当前 node_id 对应的图像路径（从 self.image_path_ctrl[node_id] 或 self.upload_paths[node_id]）
        2) 打开新窗口 MaskEditorFrame
        """
        local_image = ""
        if node_id in self.image_path_ctrl:
            local_image = self.image_path_ctrl[node_id].GetValue().strip()
        # 如果 textctrl 为空，再 fallback self.upload_paths
        if not local_image and (node_id in self.upload_paths):
            local_image = self.upload_paths[node_id]

        if not os.path.isfile(local_image):
            wx.MessageBox("无效的图像路径，无法编辑遮罩。", "错误", wx.OK | wx.ICON_ERROR)
            return
        
        # 打开编辑窗口
        dlg = MaskEditorFrame(self, self.strip_mask_suffix(local_image))
        if dlg.ShowModal() == wx.ID_OK:
            # dlg.mask_path 是最终保存的新遮罩图
            new_mask_path = dlg.mask_path
            # 更新预览
            self.upload_paths[node_id] = new_mask_path
            if node_id in self.image_path_ctrl:
                self.image_path_ctrl[node_id].SetValue(new_mask_path)
            if node_id in self.preview_bitmaps:
                self.update_preview_bitmap(node_id, new_mask_path)
        dlg.Destroy()
    
    def strip_mask_suffix(self, image_path: str) -> str:
        """
        如果 image_path 形如:
        /Users/joyy/Desktop/WechatIMG69_mask_4zPTV.png
        并且 `_mask_` 后面紧接 5 位字母数字
        => 去掉 `_mask_4zPTV`，返回原图路径
        否则原样返回
        """

        base, ext = os.path.splitext(image_path)
        # 形如 ..._mask_4zPTV (5位随机)
        # 用正则检查是否结尾有 _mask_ + 5 字母数字
        pattern = r"_mask_[A-Za-z0-9]{5}$"
        if re.search(pattern, base):
            # 去掉这个后缀
            # re.sub 将匹配到的部分替换为空字符串
            new_base = re.sub(pattern, "", base)
            return new_base + ext
        else:
            return image_path

    def on_select_image(self, event, node_id, preview_bitmap):
        """
        打开文件对话框选一张图片，在界面预览，并记录到 self.upload_paths[node_id] = local_path
        """
        wildcard = "Image files (*.png;*.jpg;*.jpeg;*.bmp;*.mp4;*.MP4;*.mov;*.avi;*.mkv;*.mp3;*.MP3;*.wav;*.WAV)|*.png;*.jpg;*.jpeg;*.bmp;*.mp4;*.MP4;*.mov;*.avi;*.mkv;*.mp3;*.MP3;*.wav;*.WAV"
        dlg = wx.FileDialog(self, message="选择本地图片/视频", wildcard=wildcard, style=wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            local_path = dlg.GetPath()
            self.on_image_selected(node_id, preview_bitmap, local_path)
        dlg.Destroy()
    
    def extract_audio(self, video_path):
        p=Path(video_path)
        out_path=str(p.with_name(p.stem+"_audio.mp3"))
        try:
            (
                ffmpeg
                .input(video_path)
                .output(out_path,format='mp3',acodec='libmp3lame',ac=2,ar='44100')
                .overwrite_output()
                .run(quiet=True)
            )
        except Exception as e:
            print(f"提取音频失败:{video_path},err={e}")
            return video_path
        return out_path
    
    def on_image_selected(self, node_id, preview_bitmap, local_path, is_folder=False):
        """
        当用户选择/拖拽图片或视频后，更新预览 & 记录路径
        """
        if node_id == "audio_path":
            ext = os.path.splitext(local_path)[1].lower()
            audio_exts={".mp3",".wav",".ogg",".flac",".aac"}
            if ext not in audio_exts:
                local_path=self.extract_audio(local_path)

        if is_folder:
            # 如果选择的是文件夹 (跟现有逻辑一样)
            app_base_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(app_base_dir, "folder_icon.png")
            if os.path.isfile(icon_path):
                icon_img = wx.Image(icon_path)
                w, h = preview_bitmap.GetSize()
                icon_img = icon_img.Scale(w, h)
                preview_bitmap.SetBitmap(wx.Bitmap(icon_img))
            else:
                w, h = preview_bitmap.GetSize()
                preview_bitmap.SetBitmap(wx.Bitmap(w, h))

            if node_id in self.image_path_ctrl:
                self.image_path_ctrl[node_id].SetValue(local_path)

            self.upload_paths[node_id] = local_path
            return

        # ---------- 如果是文件（图片/视频） -----------
        ext = os.path.splitext(local_path)[1].lower()
        VIDEO_EXTS = [".mp4", ".MP4", ".mov", ".avi", ".mkv"]  # 可按需补充
        AUDIO_EXTS = [".mp3", ".MP3", ".wav", ".WAV"]

        if ext in VIDEO_EXTS:
            # 提取视频首帧
            frame_img = self.extract_first_frame(local_path)
            if frame_img is not None:
                w, h = preview_bitmap.GetSize()
                # 缩放
                orig_w, orig_h = frame_img.GetWidth(), frame_img.GetHeight()
                ratio = min(w / float(orig_w), h / float(orig_h))
                new_w = max(1, int(orig_w * ratio))
                new_h = max(1, int(orig_h * ratio))
                frame_img = frame_img.Scale(new_w, new_h, wx.IMAGE_QUALITY_HIGH)
                preview_bitmap.SetBitmap(wx.Bitmap(frame_img))
            else:
                # 提取失败，可能用一个默认图标或留空
                w, h = preview_bitmap.GetSize()
                preview_bitmap.SetBitmap(wx.Bitmap(w, h))
        elif ext in AUDIO_EXTS:
            # 如果选择的是文件夹 (跟现有逻辑一样)
            app_base_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(app_base_dir, "audio_icon.png")
            if os.path.isfile(icon_path):
                icon_img = wx.Image(icon_path)
                w, h = preview_bitmap.GetSize()
                icon_img = icon_img.Scale(w, h)
                preview_bitmap.SetBitmap(wx.Bitmap(icon_img))
            else:
                w, h = preview_bitmap.GetSize()
                preview_bitmap.SetBitmap(wx.Bitmap(w, h))
        else:
            # 如果是图片 => 跟你原先逻辑一样
            # img = wx.Image(local_path, wx.BITMAP_TYPE_ANY)
            # w, h = preview_bitmap.GetSize()
            # img = img.Scale(w, h, wx.IMAGE_QUALITY_HIGH)
            # preview_bitmap.SetBitmap(wx.Bitmap(img))
            self.set_image_preview(preview_bitmap, local_path)

        # 更新 upload_paths 和文本框
        self.upload_paths[node_id] = local_path
        if node_id in self.image_path_ctrl:
            self.image_path_ctrl[node_id].SetValue(local_path)
    
    def set_image_preview(slef, preview_bitmap, local_path):
        """
        将 local_path 对应的图像加载后，等比缩放到 preview_bitmap 的大小并显示。
        若文件不存在或非图像，则显示空白（或可自行改成其他逻辑）。
        """
        if not os.path.isfile(local_path):
            w, h = preview_bitmap.GetSize()
            preview_bitmap.SetBitmap(wx.Bitmap(w, h))
            return

        img = wx.Image(local_path, wx.BITMAP_TYPE_ANY)
        panel_w, panel_h = preview_bitmap.GetSize()

        orig_w, orig_h = img.GetWidth(), img.GetHeight()
        if orig_w <= 0 or orig_h <= 0:
            # 如果图片无效，也直接退出
            w, h = preview_bitmap.GetSize()
            preview_bitmap.SetBitmap(wx.Bitmap(w, h))
            return

        # 计算等比缩放：找最小缩放比
        ratio = min(panel_w / float(orig_w), panel_h / float(orig_h))

        # 计算缩放后尺寸
        new_w = max(1, int(orig_w * ratio))
        new_h = max(1, int(orig_h * ratio))

        # 执行缩放
        img_resized = img.Scale(new_w, new_h, wx.IMAGE_QUALITY_HIGH)

        # 转成位图设置给预览控件
        bmp = wx.Bitmap(img_resized)
        preview_bitmap.SetBitmap(bmp)

    def extract_first_frame(self, video_path):
        """
        用 OpenCV 打开 video_path，读第一帧并转成 wx.Image
        如果成功返回 wx.Image，否则返回 None
        """
        cap = cv2.VideoCapture(video_path)
        success, frame = cap.read()
        cap.release()

        if not success or frame is None:
            return None
        
        # frame 是一个 numpy 数组，形状 (height, width, 3) BGR 格式
        height, width = frame.shape[:2]

        # OpenCV 默认是 BGR，需要转为 RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 把 numpy 数组里的数据包装到 wx.Image 对象里
        image = wx.Image(width, height)
        image.SetData(frame_rgb.tobytes())  # 每像素 3 bytes, RGB
        return image

    def get_task_data(self):
        raw_flow_api = self.workflow_choice.GetStringSelection()
        flow_api, _ = os.path.splitext(raw_flow_api)
        if flow_api == "数字人生成":
            flow_api = "DreamFace_Workflow"
        flow_inputs = {}

        if self.workflow_data:
            # 先处理 text_controls 里存储的文本/下拉框
            for node_id, fields_dict in self.text_controls.items():
                flow_inputs[node_id] = {}
                for field_name, ctrl in fields_dict.items():
                    if isinstance(ctrl, wx.Choice):
                        flow_inputs[node_id][field_name] = ctrl.GetStringSelection()
                    else:
                        flow_inputs[node_id][field_name] = ctrl.GetValue()
                    
                    # 如果有特殊逻辑，比如 lora_name -> lora_url，可以在这里加
                    if field_name == "lora_name":
                        ftp_loras_dir = "ftp://183.6.90.205:2221/mnt/NAS/mcn/loras/"
                        flow_inputs[node_id]["lora_url"] = ftp_loras_dir + flow_inputs[node_id][field_name]
            
            # ---------------------------
            # 处理 upload_paths => {"image": local_path}
            for node_id in self.preview_bitmaps.keys():
                local_image = ""
                if node_id in self.image_path_ctrl:
                    local_image = self.image_path_ctrl[node_id].GetValue().strip()
                if not local_image and (node_id in self.upload_paths):
                    local_image = self.upload_paths[node_id]

                # 如果是文件夹 => 取出所有符合扩展名的文件，放进一个列表
                if os.path.isdir(local_image):
                    all_files = []
                    valid_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", 
                                ".bmp", ".mp4", ".mov", ".avi", ".mkv"}
                    for f in os.listdir(local_image):
                        full_path = os.path.join(local_image, f)
                        if os.path.isfile(full_path):
                            ext = os.path.splitext(f)[1].lower()
                            if ext in valid_exts:
                                all_files.append(full_path)

                    # 如果想在最终 JSON 里是 list，就直接赋值为列表
                    flow_inputs[node_id] = {"image": all_files}
                else:
                    # 否则就是单文件
                    ext = os.path.splitext(local_image)[1].lower()
                    VIDEO_EXTS = [".mp4", ".MP4", ".mov", ".avi", ".mkv"]
                    if ext in VIDEO_EXTS:
                        flow_inputs[node_id] = {"video": local_image}
                    else:
                        flow_inputs[node_id] = {"image": local_image}

        return {
            "flow_api": flow_api,
            "flow_inputs": flow_inputs,
            "flow_output": self.flow_output_ctrl.GetValue(),
            "local_path": self.local_path_ctrl.GetValue()
        }
    
    def pick_random_image(self, folder):
        exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".mp4", ".MP4", ".mov", ".avi", ".mkv"}
        candidates = []
        for f in os.listdir(folder):
            full = os.path.join(folder, f)
            if os.path.isfile(full):
                _, e = os.path.splitext(f)
                if e.lower() in exts:
                    candidates.append(full)
        if not candidates:
            # fallback => maybe icon or none
            app_base_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(app_base_dir, "folder_icon.png")
        return random.choice(candidates)