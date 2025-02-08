import wx

class ConfirmDialog(wx.Dialog):
    """
    一个简单的“确认/取消”自定义对话框。
    可在此放置文本、图片、更多控件等。
    """
    def __init__(self, parent, title="确认", message="是否确定执行此操作？"):
        super().__init__(parent, title=title, size=(400, 200), style=wx.DEFAULT_DIALOG_STYLE)

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 信息文本
        lbl_message = wx.StaticText(panel, label=message)
        lbl_message.Wrap(380)  # 自动换行
        main_sizer.Add(lbl_message, 1, wx.ALL | wx.EXPAND, 15)

        # 底部按钮区域
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_ok = wx.Button(panel, wx.ID_OK, label="确认")
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, label="取消")

        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(btn_ok, 0, wx.ALL, 5)
        btn_sizer.Add(btn_cancel, 0, wx.ALL, 5)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.BOTTOM | wx.RIGHT, 10)
        panel.SetSizer(main_sizer)

        # 让对话框相对父窗口居中
        self.CentreOnParent()