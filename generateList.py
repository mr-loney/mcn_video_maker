import wx
import os
import time
import threading
import json
from wx.lib.scrolledpanel import ScrolledPanel
import concurrent.futures
import ftplib

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
                        # 读取taskuuid
                        try:
                            with open(req_path, "r", encoding="utf-8") as ff:
                                obj = json.load(ff)
                            taskuuid = obj.get("taskuuid", "")
                            # 记录
                            req_list.append((f, taskuuid, "执行中"))
                            req_files_map[taskuuid] = req_path
                        except:
                            pass

            if req_list:
                data_dict[sf] = req_list

        # 2) 拿到所有taskuuid
        all_uuids = []
        for sf, arr in data_dict.items():
            for (req_file, t_uuid, st) in arr:
                if t_uuid:
                    all_uuids.append(t_uuid)

        # 3) 调用 multiCheck => 批量获取状态
        if all_uuids:
            api = server_func.AsyncTask("MCNComfyUIFlow", {})
            # multiCheckResults 形如:
            # {
            #   "uuid": { "finish": bool, "success": bool, "data": {}, "progress": 100 },
            #   ...
            # }
            multiCheckResults = api.multiCheck(all_uuids)

            # 更新 data_dict 里 status
            for sf, arr in data_dict.items():
                new_arr = []
                for (req_file, t_uuid, st) in arr:
                    if t_uuid in multiCheckResults:
                        info = multiCheckResults[t_uuid]
                        finish  = info.get("finish", False)
                        success = info.get("success", False)
                        if not finish:
                            st = "执行中"
                        else:
                            if success:
                                st = "已完成"
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
                    new_arr.append((req_file, t_uuid, st))
                data_dict[sf] = new_arr

        return data_dict

    def download_and_remove_req(self, req_path):
        """
        读取 req_xxx.json => flows => ftp下载 => 删除 req_xxx.json
        """
        try:
            if not os.path.isfile(req_path):
                # 即便加了downloading_set，也可能用户手动删除
                return
            with open(req_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            flows = data.get("flows", [])
            # flows: [ { "flow_output": "ftp://...", "local_path": "/Users/..." }, ... ]

            # 并行下载 flows
            download_tasks = []
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
                        if ftp_path and local_path:
                            download_tasks.append(flow_executor.submit(
                                self.download_flow_output, ftp_path, local_path
                            ))

            # 等待所有下载完成
            concurrent.futures.wait(download_tasks)

            # 下载完后删除 req_xxxx.json
            # os.remove(req_path)

            # 下载完后重命名 req_xxxx.json => req_xxxx_ok.json
            base, ext = os.path.splitext(req_path)     # base="/.../req_xxxx", ext=".json"
            ok_path = base + "_ok" + ext               # => "/.../req_xxxx_ok.json"
            os.rename(req_path, ok_path)
            print(f"执行完成, 已将 {req_path} 重命名为 {ok_path}.")

        except Exception as e:
            print(f"download_and_remove_req 出错: {req_path}, {e}")
        finally:
            # 不论成功与否，都要移除以防下次阻塞
            if req_path in self.downloading_set:
                self.downloading_set.remove(req_path)

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

            # 确保 remote_path 是个目录(或可进入)
            # 这里递归下载 entire remote_path => local_dir
            self.download_entire_ftp_directory(ftp, remote_path, local_dir)

            ftp.quit()
            print(f"下载完成: {ftp_url} => {local_dir}")
        except Exception as e:
            print(f"下载失败: {ftp_url}, 错误: {e}")

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
            folder_panel.SetBackgroundColour(wx.Colour(24, 24, 24))  # 深灰
            folder_sizer = wx.BoxSizer(wx.VERTICAL)
            folder_panel.SetSizer(folder_sizer)

            # 文件夹标题
            folder_label = wx.StaticText(folder_panel, label=f"模板文件夹: {sf}")
            folder_label.SetForegroundColour(wx.Colour("gray"))
            font = folder_label.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            folder_label.SetFont(font)
            folder_sizer.Add(folder_label, 0, wx.ALL, 5)

            folder_label.Bind(
                wx.EVT_LEFT_DOWN,
                lambda evt, path=reslib_path: self.on_open_reslib(evt, path)
            )

            # 遍历 (req_file, t_uuid, st)
            for i, (req_file, t_uuid, st) in enumerate(arr):
                row_sizer = wx.BoxSizer(wx.HORIZONTAL)

                label_req = wx.StaticText(folder_panel, label=req_file)
                label_uuid = wx.StaticText(folder_panel, label=t_uuid)
                label_uuid.SetForegroundColour(wx.Colour("gray"))

                label_st = wx.StaticText(folder_panel, label=st, style=wx.ALIGN_RIGHT)

                # 不同状态不同颜色
                if st == "执行中":
                    label_st.SetForegroundColour(wx.Colour("yellow"))
                elif st == "已错误":
                    label_st.SetForegroundColour(wx.Colour("red"))
                elif st == "已完成":
                    label_st.SetForegroundColour(wx.Colour("green"))

                row_sizer.Add(label_req,  0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                row_sizer.Add(label_uuid, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
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