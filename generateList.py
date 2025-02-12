import wx
import os
import time
import threading
import json
from wx.lib.scrolledpanel import ScrolledPanel
import concurrent.futures
import ftplib
import platform
import subprocess
import sys

# 假设你有 server_func.AsyncTask("OfficialProbe", {}):
from ryry import server_func

class GenerateListFrame(wx.Frame):
    def __init__(self, parent, root_folder):
        super().__init__(parent, title="工作流状态查询", size=(600, 800))
        self.parent = parent
        self.root_folder = root_folder  # 要遍历的文件夹(含多个子文件夹)

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 列表(带滚动条)
        self.scrolled_panel = ScrolledPanel(panel, style=wx.VSCROLL)
        self.scrolled_panel.SetAutoLayout(True)
        self.scrolled_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        self.vbox_list = wx.BoxSizer(wx.VERTICAL)
        self.scrolled_panel.SetSizer(self.vbox_list)

        main_sizer.Add(self.scrolled_panel, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(main_sizer)

        # 存储 { folder_name: [ (req_file, taskuuid, status_label), ... ] }
        # 每隔5秒更新
        self.req_data = {}

        # 用于避免重复下载
        self.downloading_set = set()

        # 启动子线程，每5秒更新一次列表
        self.stop_thread = False
        self.thread = threading.Thread(target=self.check_loop)
        self.thread.start()

        # 下载线程池：5并发
        self.download_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.CentreOnParent()

    def updateFolderPath(self, root_folder):
        self.root_folder = root_folder

    def force_refresh(self):
        """ 立即执行一次扫描并刷新UI。 
            如果您需要外部手动触发一次刷新，可以实现这里。
        """
        pass

    def on_close(self, event):
        """只隐藏窗体，不销毁、不中断扫描线程。"""
        self.Hide()

    def check_loop(self):
        """
        子线程:
          1) 每隔5秒遍历 self.root_folder 下所有子文件夹, 找 reslib/req_xxxxx.json => 收集
          2) multiCheck => 获取finish/success
          3) 主线程更新UI
          4) 如果finish=true&success=true => 异步下载 => 删除req_xxxx.json (避免重复)
        """
        while not self.stop_thread:
            new_info = self.scan_folders_and_parse()
            wx.CallAfter(self.update_ui, new_info)
            # sleep 5s
            for _ in range(5):
                if self.stop_thread:
                    break
                time.sleep(1)

    def scan_folders_and_parse(self):
        """
        遍历 root_folder 下子文件夹:
          如果子文件夹有 reslib/req_xxxxx.json => 解析 taskuuid
        返回 { subfolder: [ (req_file, taskuuid, status), ... ], ... }
        其中 status 初始填"执行中"
        """
        data_dict = {}

        if not os.path.isdir(self.root_folder):
            return data_dict

        subfolders = os.listdir(self.root_folder)
        req_files_map = {}  # { taskuuid: req_path } => 用于后面下载

        for sf in subfolders:
            folder_path = os.path.join(self.root_folder, sf)
            if not os.path.isdir(folder_path):
                continue

            reslib_path = os.path.join(folder_path, "reslib")
            if not os.path.isdir(reslib_path):
                continue

            # 找 req_xxxxx.json
            req_list = []
            for f in os.listdir(reslib_path):
                if f.startswith("res_") and f.endswith(".json"):
                    req_path = os.path.join(reslib_path, f)
                    if os.path.isfile(req_path):
                        try:
                            with open(req_path, "r", encoding="utf-8") as ff:
                                obj = json.load(ff)
                            taskuuid = obj.get("taskuuid", "")

                            if f.endswith("_ok.json"):
                                # 已完成的文件 => 状态“已完成”
                                req_list.append((f, taskuuid, "已完成", req_path))
                                # 不放进 req_files_map，所以后续不会 multiCheck 也不会下载
                            else:
                                # 普通 .json => 状态初始“执行中”
                                req_list.append((f, taskuuid, "执行中", req_path))
                                # 加入 req_files_map，用于 multiCheck 以及下载
                                if taskuuid:
                                    req_files_map[taskuuid] = req_path
                        except Exception as e:
                            print(f"读取 {req_path} 出错: {e}")

            if req_list:
                data_dict[sf] = req_list

        # 2) 拿到所有taskuuid
        # all_uuids = []
        # for sf, arr in data_dict.items():
        #     for (req_file, t_uuid, st) in arr:
        #         if t_uuid:
        #             all_uuids.append(t_uuid)
        all_uuids = list(req_files_map.keys())

        # 3) 调用 multiCheck => 批量获取状态
        if all_uuids:
            api = server_func.AsyncTask("MCNComfyUIFlow", {})
            multiCheckResults = api.multiCheck(all_uuids)

            # 更新 data_dict 里 status
            for sf, arr in data_dict.items():
                new_arr = []
                for (req_file, t_uuid, st, abs_path) in arr:
                    # 如果是 _ok.json => 已完成，不变
                    if req_file.endswith("_ok.json"):
                        new_arr.append((req_file, t_uuid, st, abs_path))
                        continue
                    
                    # 否则是普通 req_xxxx.json => 根据 multiCheck 更新状态
                    if t_uuid in multiCheckResults:
                        info = multiCheckResults[t_uuid]
                        finish  = info.get("finish", False)
                        success = info.get("success", False)
                        if not finish:
                            st = "执行中"
                        else:
                            if success:
                                st = "已返回(下载中)"
                                # 异步下载 => remove req
                                req_path = req_files_map.get(t_uuid, "")
                                if req_path:
                                    # 若该 req_path 不在 downloading_set，才下载
                                    if req_path not in self.downloading_set:
                                        self.downloading_set.add(req_path)
                                        self.download_pool.submit(
                                            self.download_and_remove_req, req_path
                                        )
                            else:
                                st = "已错误"
                    new_arr.append((req_file, t_uuid, st, abs_path))
                data_dict[sf] = new_arr

        return data_dict

    def download_and_remove_req(self, req_path):
        """
        读取 req_xxx.json => flows => ftp下载 => 删除 req_xxx.json
        """
        try:
            if not os.path.isfile(req_path):
                return  # 如果请求的 JSON 文件不存在，直接跳过

            # 读取 JSON 文件中的数据
            with open(req_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            flows = data.get("flows", [])
            download_tasks = []

            # 并行下载 flows 中的资源
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as flow_executor:
                for flow in flows:
                    flow_output = flow.get("flow_output", "")
                    if '#' in flow_output:
                        print("#中继输出节点")
                    else:
                        ftp_path = "ftp://183.6.90.205:2221/mnt/NAS/mcn/" + flow_output
                        local_path = flow.get("local_path", "")

                        # 如果 local_path 不为空，则拼上时间戳(时)
                        if local_path and "/reslib/" in local_path:
                            time_stamp = time.strftime("%Y%m%d_%H")
                            local_path = f"{local_path}_{time_stamp}"

                        # 资源文件已经存在就跳过下载
                        if not self.is_file_already_downloaded(local_path):
                            if ftp_path and local_path:
                                download_tasks.append(flow_executor.submit(
                                    self.download_flow_output, ftp_path, local_path
                                ))

            # 等待所有下载完成
            concurrent.futures.wait(download_tasks)

            # 下载完成后将 req 文件重命名
            base, ext = os.path.splitext(req_path)
            ok_path = base + "_ok" + ext
            os.rename(req_path, ok_path)
            print(f"执行完成, 已将 {req_path} 重命名为 {ok_path}.")

        except Exception as e:
            print(f"download_and_remove_req 出错: {req_path}, {e}")
        finally:
            # 移除当前请求路径，防止下次阻塞
            if req_path in self.downloading_set:
                self.downloading_set.remove(req_path)

    def is_file_already_downloaded(self, local_path):
        """
        检查文件是否已经存在（用于避免重复下载）
        """
        return os.path.exists(local_path)  # 如果文件已存在，返回 True

    def download_flow_output(self, ftp_url, local_dir):
        """
        下载 ftp_url(一个 FTP 目录) 下的所有文件/文件夹 => local_dir。
        示例假设:
        ftp_url 形如 ftp://183.6.90.205:2221/mnt/NAS/mcn/xxxx
        最终将 xxxx 目录的所有文件/子目录都下载到 local_dir。
        """

        try:
            # 1) 确保 local_dir 存在
            os.makedirs(local_dir, exist_ok=True)

            # 2) 解析 ftp_url => ftp_host, ftp_port=2221, remote_path
            prefix = "ftp://"
            if not ftp_url.startswith(prefix):
                print(f"非法 ftp_url: {ftp_url}")
                return

            # ftp://183.6.90.205:2221/mnt/NAS/mcn/xxxxx
            without_prefix = ftp_url[len(prefix):]  # 183.6.90.205:2221/mnt/...
            # 先 split 第一个 / 之前 => host:port
            parts = without_prefix.split("/", 1)
            host_port = parts[0]  # e.g. 183.6.90.205:2221
            remote_path = "/" + parts[1] if len(parts) > 1 else "/"

            # 分析 host和port
            if ":" in host_port:
                ftp_host, ftp_port_str = host_port.split(":", 1)
                ftp_port = int(ftp_port_str)
            else:
                ftp_host = host_port
                ftp_port = 21

            ftp_user = "mcn"
            ftp_pass = "meco@2024+"

            # 3) 连接 FTP
            ftp = ftplib.FTP()
            ftp.connect(ftp_host, ftp_port, timeout=30)
            ftp.login(ftp_user, ftp_pass)

            # 4) 调用新的并行下载函数
            self.download_entire_ftp_directory_parallel(
                ftp_host, ftp_port,
                ftp_user, ftp_pass,
                remote_path, local_dir
            )
            
            ftp.quit()
            print(f"下载完成: {ftp_url} => {local_dir}")
        except Exception as e:
            print(f"下载失败: {ftp_url}, 错误: {e}")

    def download_entire_ftp_directory_parallel(self, ftp_host, ftp_port, ftp_user, ftp_pass,
                                           remote_dir, local_dir):
        """
        并行下载 remote_dir 下的所有文件(4并发)，对子目录递归处理(串行)。
        每个文件使用新的FTP连接来下载，避免多线程冲突。
        """
        # 确保本地目录存在
        os.makedirs(local_dir, exist_ok=True)

        # 先用一次性FTP连接列出当前层
        ftp = ftplib.FTP()
        ftp.connect(ftp_host, ftp_port, timeout=30)
        ftp.login(ftp_user, ftp_pass)
        try:
            ftp.cwd(remote_dir)
        except Exception as e:
            print(f"无法进入目录: {remote_dir}, 错误: {e}")
            ftp.quit()
            return

        items = ftp.nlst()  # 当前层所有项
        ftp.quit()

        file_list = []
        dir_list = []
        # 分辨每个 item 是文件还是子目录
        for item in items:
            if item in (".", ".."):
                continue
            remote_item_path = remote_dir.rstrip("/") + "/" + item
            local_item_path = os.path.join(local_dir, item)

            if self.is_ftp_directory(ftp_host, ftp_port, ftp_user, ftp_pass, remote_item_path):
                # 是目录
                dir_list.append((remote_item_path, local_item_path))
            else:
                # 是文件
                file_list.append((remote_item_path, local_item_path))

        # 并行下载 file_list(4线程)
        max_workers = 4
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for (rpath, lpath) in file_list:
                futures.append(executor.submit(
                    self.download_single_file_new_ftp,
                    ftp_host, ftp_port, ftp_user, ftp_pass,
                    rpath, lpath
                ))
            concurrent.futures.wait(futures)

        # 递归处理子目录(串行) => 你也可以把它并行，但需更多逻辑
        for (sub_rpath, sub_lpath) in dir_list:
            self.download_entire_ftp_directory_parallel(
                ftp_host, ftp_port,
                ftp_user, ftp_pass,
                sub_rpath, sub_lpath
            )
    
    def is_ftp_directory(self, ftp_host, ftp_port, ftp_user, ftp_pass, path):
        """
        判断 path 是否目录:
        - 尝试 ftp.cwd(path)，若成功 => 目录；失败 => 文件/无权限
        """
        try:
            ftp = ftplib.FTP()
            ftp.connect(ftp_host, ftp_port, timeout=30)
            ftp.login(ftp_user, ftp_pass)
            ftp.cwd(path)
            ftp.quit()
            return True
        except:
            return False
    
    def download_single_file_new_ftp(self, ftp_host, ftp_port, ftp_user, ftp_pass,
                                 remote_file_path, local_file_path):
        """
        每次下载一个文件都新建 FTP 连接 => 方便多线程。
        """
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        try:
            ftp = ftplib.FTP()
            ftp.connect(ftp_host, ftp_port, timeout=30)
            ftp.login(ftp_user, ftp_pass)

            remote_dir = os.path.dirname(remote_file_path)
            base_name = os.path.basename(remote_file_path)
            ftp.cwd(remote_dir)

            print(f"[Thread] Downloading file => {remote_file_path} => {local_file_path}")
            with open(local_file_path, "wb") as f:
                ftp.retrbinary(f"RETR " + base_name, f.write)
            ftp.quit()
        except Exception as e:
            print(f"下载文件出错: {remote_file_path}, 错误: {e}")

    def download_entire_ftp_directory(self, ftp, remote_dir, local_dir):
        """
        递归下载 FTP 上 remote_dir 下的所有文件/文件夹 => local_dir
        """
        try:
            # 1) 尝试 cwd
            ftp.cwd(remote_dir)
        except ftplib.error_perm as e:
            # 如果不能进入 => 可能 remote_dir 是个文件
            # 也可能无权限
            print(f"无法进入目录: {remote_dir}, 尝试作为文件下载. err={e}")
            return

        # 2) 获取当前目录下文件/子目录
        items = ftp.nlst()  # 可能包含文件或目录

        for item in items:
            if item in ('.', '..'):
                continue

            remote_item_path = remote_dir.rstrip('/') + '/' + item
            local_item_path = os.path.join(local_dir, item)

            try:
                ftp.cwd(remote_item_path)
                # 如果成功 => 是目录 => 回退
                ftp.cwd(remote_dir)

                os.makedirs(local_item_path, exist_ok=True)
                self.download_entire_ftp_directory(ftp, remote_item_path, local_item_path)
            except ftplib.error_perm:
                # 是文件
                self.download_single_file(ftp, remote_item_path, local_item_path)

    def download_single_file(self, ftp, remote_file_path, local_file_path):
        """
        从FTP上下载 single file 到 local_file_path
        """
        local_dir = os.path.dirname(local_file_path)
        os.makedirs(local_dir, exist_ok=True)

        remote_dir = os.path.dirname(remote_file_path)
        base_name = os.path.basename(remote_file_path)

        ftp.cwd(remote_dir)
        print(f"Downloading file: {remote_file_path} => {local_file_path}")
        with open(local_file_path, "wb") as f:
            ftp.retrbinary(f"RETR {base_name}", f.write)

    def update_ui(self, new_info):
        """
        主线程里刷新UI: { folder_name: [ (req_file, taskuuid, status), ... ] }
        """
        # 1) 清空原UI
        for child in self.vbox_list.GetChildren():
            child.DeleteWindows()
        self.vbox_list.Clear(True)

        # 2) 构建新的UI
        for sf, arr in new_info.items():
            # 文件夹的绝对路径
            folder_path = os.path.join(self.root_folder, sf)
            reslib_path = os.path.join(folder_path, "reslib")

            # 用一个 panel + boxsizer 做灰色背景
            folder_panel = wx.Panel(self.scrolled_panel)
            if self.is_dark_mode():
                folder_panel.SetBackgroundColour(wx.Colour(24, 24, 24))  # 深灰
            else:
                folder_panel.SetBackgroundColour(wx.Colour(180, 180, 180))  # 深灰
            folder_sizer = wx.BoxSizer(wx.VERTICAL)
            folder_panel.SetSizer(folder_sizer)

            # 水平布局放置 folder_label 和 clear_label
            top_sizer = wx.BoxSizer(wx.HORIZONTAL)  # 水平布局

            # 文件夹标题
            folder_label = wx.StaticText(folder_panel, label=f"模板文件夹: {sf} [Open]")
            folder_label.SetForegroundColour(wx.Colour("gray"))
            if self.is_dark_mode():
                folder_label.SetForegroundColour(wx.Colour("gray"))
            else:
                folder_label.SetForegroundColour(wx.Colour("black"))
            font = folder_label.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            folder_label.SetFont(font)
            
            top_sizer.Add(folder_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

            folder_label.Bind(
                wx.EVT_LEFT_DOWN,
                lambda evt, path=reslib_path: self.on_open_reslib(evt, path)
            )

            # 添加[清空任务]标签
            clear_label = wx.StaticText(folder_panel, label="[清空任务]")
            if self.is_dark_mode():
                clear_label.SetForegroundColour(wx.Colour("gray"))
            else:
                clear_label.SetForegroundColour(wx.Colour("#444444"))
            font = folder_label.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            clear_label.SetFont(font)
            clear_label.Bind(
                wx.EVT_LEFT_DOWN,
                lambda evt, folder=sf: self.clear_folder_tasks(evt, folder)
            )

            # 将 [清空任务] 放置到右边
            right_sizer = wx.BoxSizer(wx.HORIZONTAL)
            right_sizer.AddStretchSpacer(1)  # 添加一个弹性间隔，使清空任务靠右
            right_sizer.Add(clear_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
            
            # 添加 right_sizer 到 top_sizer
            top_sizer.Add(right_sizer, 1, wx.EXPAND | wx.ALL, 0)

            # 将水平布局添加到垂直布局
            folder_sizer.Add(top_sizer, 0, wx.EXPAND | wx.ALL, 0)

            # 遍历 (req_file, t_uuid, st)
            for i, (req_file, t_uuid, st, abs_path) in enumerate(arr):
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)

                # 只显示 t_uuid 后6位
                # short_uuid = t_uuid[-6:] if len(t_uuid) > 6 else t_uuid
                # 先从 JSON 中尝试获取 cmd_title
                cmd_title = None
                if os.path.isfile(abs_path):
                    try:
                        with open(abs_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        cmd_title = data.get("cmd_title", None)
                    except Exception as e:
                        print(f"读取 JSON 出错或无 cmd_title: {e}")

                if cmd_title:
                    max_length = 30
                    if len(cmd_title) > max_length:
                        # 预留 3 个字符给 "..."，
                        # 因此只保留前 35 个字符 + "..."
                        cmd_title = cmd_title[:(max_length-3)] + "..."

                # 如果存在 cmd_title，则用它作为显示文本；否则用 t_uuid
                display_text = cmd_title if cmd_title else t_uuid
                
                label_req = wx.StaticText(folder_panel, label=req_file)
                label_uuid = wx.StaticText(folder_panel, label=display_text)

                if self.is_dark_mode():
                    label_uuid.SetForegroundColour(wx.Colour("gray"))
                else:
                    label_uuid.SetForegroundColour(wx.Colour("#444444"))

                label_st = wx.StaticText(folder_panel, label=st, style=wx.ALIGN_RIGHT)

                # 不同状态不同颜色
                if st == "执行中":
                    label_st.SetForegroundColour(wx.Colour("yellow"))
                elif st == "已错误":
                    label_st.SetForegroundColour(wx.Colour("red"))
                elif st == "已返回(下载中)":
                    label_st.SetForegroundColour(wx.Colour("yellow"))
                elif st == "已完成":
                    label_st.SetForegroundColour(wx.Colour("green"))

                row_sizer.Add(label_req,  0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                row_sizer.Add(label_uuid, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                # 当状态为“已完成”或“已错误”时，增加“删除”按钮
                if st in ("已完成", "已错误"):
                    delete_label = wx.StaticText(folder_panel, label="[删除]")
                    if self.is_dark_mode():
                        delete_label.SetForegroundColour(wx.Colour("gray"))
                    else:
                        delete_label.SetForegroundColour(wx.Colour("#444444"))
                    # 点击后执行删除方法
                    delete_label.Bind(
                        wx.EVT_LEFT_DOWN,
                        lambda evt, p=abs_path, folder=sf: self.on_delete_req(evt, p, folder)
                    )
                    row_sizer.Add(delete_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                # 当状态为“已完成”时，额外增加“打开”按钮
                if st == "已完成":
                    open_label = wx.StaticText(folder_panel, label="[打开]")
                    if self.is_dark_mode():
                        open_label.SetForegroundColour(wx.Colour("gray"))
                    else:
                        open_label.SetForegroundColour(wx.Colour("#444444"))
                    # 假设: req_file="res_123.json" => base_name="res_123"
                    open_label.Bind(
                        wx.EVT_LEFT_DOWN,
                        lambda evt, json_path=abs_path: self.on_open_local_path(evt, json_path)
                    )
                    row_sizer.Add(open_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                row_sizer.AddStretchSpacer(1)
                row_sizer.Add(label_st,   0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

                folder_sizer.Add(row_sizer, 0, wx.EXPAND | wx.ALL, 2)

                # 如果不是最后一条 => 加条分割线
                if i < len(arr) - 1:
                    line = wx.StaticLine(folder_panel)
                    folder_sizer.Add(line, 0, wx.EXPAND | wx.ALL, 2)

            # folder_panel 加到最外层
            self.vbox_list.Add(folder_panel, 0, wx.EXPAND | wx.ALL, 5)

        # 3) 重新布局
        self.scrolled_panel.Layout()
        self.scrolled_panel.SetupScrolling(scroll_x=False, scroll_y=True)

    def clear_folder_tasks(self, event, folder_name):
        """
        清空文件夹下所有 res_xxxx.json 文件
        """
        folder_path = os.path.join(self.root_folder, folder_name, "reslib")
        if not os.path.isdir(folder_path):
            wx.MessageBox(f"文件夹不存在: {folder_path}", "错误", wx.OK | wx.ICON_ERROR)
            return

        try:
            for file_name in os.listdir(folder_path):
                if file_name.startswith("res_") and file_name.endswith(".json"):
                    file_path = os.path.join(folder_path, file_name)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"已删除: {file_path}")
            # wx.MessageBox(f"已清空文件夹 {folder_name} 下的所有任务。", "清空成功", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"清空失败: {e}", "错误", wx.OK | wx.ICON_ERROR)

        # 清空文件后刷新 UI
        new_info = self.scan_folders_and_parse()
        self.update_ui(new_info)
    
    def on_delete_req(self, event, req_path, folder_name):
        """
        删除 req_path 文件，并刷新列表
        """
        if not os.path.isfile(req_path):
            wx.MessageBox(f"文件不存在: {req_path}", "错误", wx.OK | wx.ICON_ERROR)
            return
        
        try:
            os.remove(req_path)
            # wx.MessageBox(f"已删除 {req_path}", "删除成功", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"删除失败: {e}", "错误", wx.OK | wx.ICON_ERROR)
            return

        # 删除后强制刷新
        new_info = self.scan_folders_and_parse()
        self.update_ui(new_info)
    
    def on_open_local_path(self, event, json_path):
        """
        打开 flows[0]["local_path"] 字段指定的目录(可能不完整)，
        实际需要搜索“带后缀”的文件夹。
        """
        if not os.path.isfile(json_path):
            wx.MessageBox(f"无法找到文件: {json_path}", "错误", wx.OK | wx.ICON_ERROR)
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            wx.MessageBox(f"读取 JSON 出错: {e}", "错误", wx.OK | wx.ICON_ERROR)
            return

        flows = data.get("flows", [])
        if not flows:
            wx.MessageBox("JSON 中没有 flows，无法定位 local_path", "提示", wx.OK | wx.ICON_INFORMATION)
            return

        # 这里只演示获取第一个 flow 的 local_path
        flow = flows[0]
        local_path = flow.get("local_path", "")
        if not local_path:
            wx.MessageBox("未找到 local_path 字段", "提示", wx.OK | wx.ICON_INFORMATION)
            return

        # local_path 形如：/Users/joyy/Desktop/testlib/fddgfdgf_mqRsK/reslib/res_VGQM01
        # 但实际要打开：res_VGQM01_XXXX

        parent_dir = os.path.dirname(local_path)      # => /Users/joyy/Desktop/testlib/fddgfdgf_mqRsK/reslib
        base_name = os.path.basename(local_path)      # => res_VGQM01

        if not os.path.isdir(parent_dir):
            wx.MessageBox(f"父目录不存在: {parent_dir}", "错误", wx.OK | wx.ICON_ERROR)
            return

        # 在 parent_dir 下搜索以 base_name 开头的所有文件夹
        candidates = []
        for d in os.listdir(parent_dir):
            full_path = os.path.join(parent_dir, d)
            if os.path.isdir(full_path) and d.startswith(base_name):
                candidates.append(full_path)

        if not candidates:
            wx.MessageBox(
                f"在 {parent_dir} 中未找到以 '{base_name}' 开头的文件夹！",
                "提示",
                wx.OK | wx.ICON_INFORMATION
            )
            return

        # 如果只找到一个 => 打开它
        if len(candidates) == 1:
            target_folder = candidates[0]
        else:
            # 如果找到多个，按需决定：这里演示“打开最新修改的一个”
            target_folder = max(candidates, key=os.path.getmtime)

        self.open_folder_in_explorer(target_folder)

    def open_folder_in_explorer(self, folder_path):
        import platform
        import subprocess
        pf = platform.system()
        if pf == "Windows":
            os.startfile(folder_path)
        elif pf == "Darwin":
            subprocess.run(["open", folder_path])
        else:
            subprocess.run(["xdg-open", folder_path])

    def on_open_reslib(self, event, folder_path):
        """
        打开 reslib 文件夹 (folder_path) 在操作系统的文件浏览器中
        """
        if not os.path.isdir(folder_path):
            wx.MessageBox(f"路径不存在: {folder_path}", "错误", wx.OK | wx.ICON_ERROR)
            return

        import platform
        import subprocess
        pf = platform.system()
        if pf == "Windows":
            os.startfile(folder_path)
        elif pf == "Darwin":
            subprocess.run(["open", folder_path])
        else:
            subprocess.run(["xdg-open", folder_path])

    def is_dark_mode(self):
        """
        检测当前系统(Windows / macOS)是否使用深色模式。
        返回 True 表示深色模式，False 表示浅色模式。
        对其它系统默认返回 False。
        """
        os_name = platform.system()
        
        if os_name == "Darwin":
            # macOS 检测
            return self.is_dark_mode_macos()
        elif os_name == "Windows":
            # Windows 检测
            return self.is_dark_mode_windows()
        else:
            # 其它系统暂不处理，默认认为浅色
            return False

    def is_dark_mode_macos(self):
        """
        macOS 下，通过 `defaults read -g AppleInterfaceStyle` 判断
        如果返回 `Dark` 则是深色模式，否则浅色。
        """
        try:
            out = subprocess.check_output(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                stderr=subprocess.STDOUT
            ).strip()
            return (out == b"Dark")
        except subprocess.CalledProcessError:
            # 没有此 key 或调用出错 => 浅色模式
            return False

    def is_dark_mode_windows(self):
        """
        Windows 下通过注册表:
        HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize
        - AppsUseLightTheme = 0 => 深色, 1 => 浅色
        或
        - SystemUsesLightTheme = 0 => 深色, 1 => 浅色
        根据需要可检测“AppsUseLightTheme”或“SystemUsesLightTheme”。
        若无法读取则默认浅色。
        """
        try:
            import winreg  # Python 自带 Windows-only
            
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            # 我们以 AppsUseLightTheme 为例；SystemUsesLightTheme 同理
            value_name = "AppsUseLightTheme"
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
                value, regtype = winreg.QueryValueEx(key, value_name)
                # value = 1 表示浅色，0 表示深色
                return (value == 0)  # 0 => 深色 => return True
        except:
            # 如果读注册表出错，就返回 False（默认浅色）
            return False