import wx
import wx.html2

class DeepSeekFrame(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Deepseek", size=(800, 800))
        self.parent = parent

        # 创建主面板
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 设置面板的背景颜色为 #292a2d
        panel.SetBackgroundColour('#292a2d')

        # 创建 WebView 并加载百度网站
        self.webview = wx.html2.WebView.New(panel)
        self.webview.SetBackgroundColour('#292a2d')
        self.webview.LoadURL("https://chat.deepseek.com")
        
        # 将 WebView 添加到布局中
        main_sizer.Add(self.webview, 1, flag=wx.EXPAND)

        # 设置面板的布局
        panel.SetSizer(main_sizer)

        # 初始化 URL 变量
        self.last_url = None

        # 绑定网页链接变化事件
        self.webview.Bind(wx.html2.EVT_WEBVIEW_NAVIGATED, self.on_url_change)

        # 创建并启动定时器
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.check_url, self.timer)
        # self.timer.Start(1000)  # 每秒检查一次

        # 中心化窗口
        self.CentreOnParent()

        # 显示窗口
        self.Show()

    def on_url_change(self, event):
        """ 网页链接变化时触发的事件 """
        current_url = event.GetURL()
        self.last_url = current_url  # 更新上次的 URL

    def check_url(self, event):
        """ 定时检查当前的 URL 与上次的 URL 是否不同 """
        current_url = self.webview.GetCurrentURL()

        if current_url != self.last_url:
            print(f"网页链接已更改为: {current_url}")
            self.last_url = current_url  # 更新上次的 URL
    
    def Destroy(self):
        """ 确保在销毁时停止定时器 """
        self.timer.Stop()
        return super().Destroy()