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

import matplotlib
matplotlib.use("WXAgg")
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure

from pydub import AudioSegment

class CustomMessageDialog(wx.Dialog):
    def __init__(self, parent, message, title="提示", style=wx.OK | wx.ICON_INFORMATION):
        super().__init__(parent, title=title, size=(300, 150))

        # 创建内容
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 消息内容居中
        message_label = wx.StaticText(panel, label=message, style=wx.ALIGN_CENTER)
        message_label.Wrap(280)  # 自动换行
        vbox.AddStretchSpacer(1)  # 添加一个伸展间隔，确保垂直居中
        vbox.Add(message_label, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        vbox.AddStretchSpacer(1)  # 添加一个伸展间隔，确保垂直居中

        # 确定按钮
        btn_ok = wx.Button(panel, label="确定")
        btn_ok.Bind(wx.EVT_BUTTON, self.on_close)
        vbox.Add(btn_ok, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(vbox)
        self.CentreOnParent()

    def on_close(self, event):
        self.EndModal(wx.ID_OK)

# 使用自定义对话框
def show_custom_message_dialog(parent, message, title="提示"):
    dialog = CustomMessageDialog(parent, message, title)
    parent_pos = parent.GetPosition()
    parent_size = parent.GetSize()
    dialog_size = dialog.GetSize()

    # 动态计算对话框位置
    dialog_x = parent_pos.x + (parent_size.width - dialog_size.width) // 2
    dialog_y = parent_pos.y + (parent_size.height - dialog_size.height) // 2
    dialog.SetPosition((dialog_x, dialog_y))

    dialog.ShowModal()
    dialog.Destroy()