import os, json, re, shutil
import asyncio
from ryry import server_func
from ryry import ryry_widget
import wx.lib.newevent
import threading

class TaskStatusWindow(wx.Frame):
    def __init__(self, parent, manager):
        super().__init__(parent, title="导出任务状态", size=(300, 400))
        self.panel = wx.Panel(self)
        self.manager = manager
        self.status_listbox = wx.ListBox(self.panel, pos=(10, 10), size=(280, 340))
        
        # 获取任务状态并显示
        self.update_task_status()
        
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer_update, self.timer)
        self.timer.Start(10000)  # 每秒钟刷新一次任务状态
        self.Bind(EVT_EXPORT_COMPLETE, self.on_export_complete)
        
    def on_timer_update(self, event):
        """定时更新任务状态"""
        self.update_task_status()

    def on_export_complete(self, event):
        """收到任务完成事件后更新任务状态"""
        self.update_task_status()

    def update_task_status(self):
        """更新任务状态显示"""
        task_status = []
        for task in self.manager.all_task:
            if task.is_start == False:
                task_status.append(f"任务 {task.name}：   ⌛️")
            elif task.is_start and not task.is_end:
                task_status.append(f"任务 {task.name}：   ⏰处理中⏰")
            elif task.is_end and task.error_msg:
                task_status.append(f"任务 {task.name}：   ❌ - {task.error_msg}")
            else:
                task_status.append(f"任务 {task.name}：   ✅")
        
        # 在列表框中显示任务状态
        self.status_listbox.SetItems(task_status)
        
    def close(self):
        """关闭窗口时停止定时器"""
        self.timer.Stop()
        self.Destroy()

ExportCompleteEvent, EVT_EXPORT_COMPLETE = wx.lib.newevent.NewEvent()
class ExportTaskManager:
    def __init__(self, parent_window):
        self.task_queue = []  # 队列，用于存储任务
        self.all_task = []  # 用于展示
        self.is_start = False
        self.is_end = False
        self.parent_window = parent_window
        self.timer = wx.Timer(parent_window)
        parent_window.Bind(wx.EVT_TIMER, self.on_timer_update, self.timer)
        self.timer_tik = 0
        self.all_cnt = 0
        self.current_index = 0

    def on_timer_update(self, event):
        self.timer_tik += 1
        if self.timer_tik > 3:
            self.timer_tik = 0
        wx.CallAfter(wx.PostEvent, self.parent_window, ExportCompleteEvent(
                is_start=self.is_start, 
                is_end=self.is_end, 
                msg=f"进度: {self.current_index}/{self.all_cnt}" + [".","..","...","...."][self.timer_tik]))
        
    async def process_tasks(self):
        print("========== 开启生成")
        while self.task_queue:
            task = self.task_queue.pop(0)  # 取出一个任务
            self.current_index+=1
            await task()
        print("========== 全部结束")
        self.stop()

    def add_task(self, task):
        """将任务加入队列"""
        self.task_queue.append(task)
        self.all_task.append(task)
        self.all_cnt+=1

    def start(self):
        """开始异步处理任务"""
        if not self.is_start and len(self.task_queue) > 0:
            self.is_start = True
            self.is_end = False
            self.timer.Start(300)  # 每0.3秒钟刷新一次任务状态
            wx.CallAfter(self.start_async_task)
            
    def start_async_task(self):
        threading.Thread(target=self.run_async_task, daemon=True).start()

    def run_async_task(self):
        """在新的线程中运行 asyncio 事件循环"""
        loop = asyncio.new_event_loop()  # 创建新的事件循环
        asyncio.set_event_loop(loop)  # 设置为当前线程的事件循环
        loop.run_until_complete(self.process_tasks())  # 运行异步任务
        
    def stop(self):
        self.is_end = True
        self.timer.Stop()
        wx.CallAfter(wx.PostEvent, self.parent_window, ExportCompleteEvent(
                is_start=self.is_start, 
                is_end=self.is_end, 
                msg=f"进度: {self.current_index}/{self.all_cnt}"))
        self.is_start = False

class ExportTask:
    def __init__(self, folder, config, name, folder_picker):
        self.folder = folder
        self.config = config
        self.name = name
        self.folder_picker = folder_picker
        self.error_msg = ""
        self.is_start = False
        self.is_end = False

    async def __call__(self):
        print("=== task start")
        self.is_start = True
        folder_path = self.folder_picker.GetPath()
        full_path = os.path.join(folder_path, self.folder)
        config_path = os.path.join(full_path, "config.json")

        if not os.path.exists(config_path):
            self.is_end = True
            self.error_msg = f"config_path not found"
            return

        with open(config_path, 'r') as config_file:
            config = json.load(config_file)

        ftp_folder_name = config.get("ftp_folder_name", "")
        social_account = config.get("social_account", "")
        if not ftp_folder_name or not social_account:
            self.is_end = True
            self.error_msg = f"social_account is empty or ftp_folder_name is empty"
            return

        base_ftp_path = "ftp://183.6.90.205:2221/mnt/NAS/mcn/aigclib/" + ftp_folder_name + "/{userid}"
        config_str = json.dumps(config)
        config_str = config_str.replace(base_ftp_path, full_path)
        config = json.loads(config_str)

        output_dir = os.path.join(full_path, "output")
        
        try:
            # 导出视频
            cnt = export(config, output_dir)
        except Exception as e:
            self.error_msg = f"错误: {e}"
        self.is_end = True
        print("=== task end")
    
def export(config, output_dir):
    print("=== template start")
    config["output"] = output_dir
    if os.path.exists(output_dir) == False:
        os.makedirs(output_dir)
    print("=== start GenVideo_Template2")
    ryry_widget.installWidget("GenVideo_Template2")
    data = server_func.Task("GenVideo_Template2", [
        {
            "params": config,
            "task_id": config["ftp_folder_name"]
        }
    ]).call()
    print("=== end GenVideo_Template2")
    if len(data[0].get("url", "")) > 0:
        result_file = os.path.join(output_dir, "new.mp4")
        if os.path.exists(result_file):
            def get_next_video_filename(folder_path):
                pattern = re.compile(r'result_(\d+)\.mp4')
                files = os.listdir(folder_path)
                ids = []
                for file in files:
                    match = pattern.match(file)
                    if match:
                        ids.append(int(match.group(1)))
                if not ids:
                    return 'result_1.mp4'
                next_id = max(ids) + 1
                return f'result_{next_id}.mp4'
            shutil.copyfile(result_file, os.path.join(output_dir, get_next_video_filename(output_dir)))
            os.remove(result_file)
            print("export video success.")
        else:
            print("export video success, but video not found!")
    else:
        print("export video fail !")
        print(data)
    print("=== template end")