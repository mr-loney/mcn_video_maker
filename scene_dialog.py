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

class SceneSelectionDialog(wx.Dialog):
    def __init__(self, parent, num_scenes, last_scene_choices, initial_choices=None):
        super().__init__(parent, title="选择每一幕的场景类型", size=(400, 450), style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)

        self.scene_choices = initial_choices or ["全屏数字人"] * num_scenes

        # 创建滚动面板
        scrolled_panel = scrolled.ScrolledPanel(self, size=(400, 300), style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        scrolled_panel.SetAutoLayout(1)
        scrolled_panel.SetupScrolling(scroll_x=False, scroll_y=True)

        vbox = wx.BoxSizer(wx.VERTICAL)

        self.dropdowns = []  # 保存所有下拉框
        for i in range(num_scenes):
            hbox = wx.BoxSizer(wx.HORIZONTAL)

            label = wx.StaticText(scrolled_panel, label=f"第{i + 1}幕:")
            hbox.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

            choices = [
                "全屏数字人",
                "全屏内容",
                "左上数字人头像+全屏内容",
                "右上数字人头像+全屏内容",
                "左下数字人头像+全屏内容",
                "右下数字人头像+全屏内容",
                "全屏数字人+浮窗",
                "全屏内容+浮窗",
            ]
            dropdown = wx.Choice(scrolled_panel, choices=choices)
            if last_scene_choices and len(last_scene_choices) > 0:
                if i < len(last_scene_choices):
                    dropdown.SetSelection(choices.index(last_scene_choices[i]))
                else:
                    dropdown.SetSelection(choices.index(self.scene_choices[i]))
            else:
                dropdown.SetSelection(choices.index(self.scene_choices[i]))
            dropdown.Bind(wx.EVT_CHOICE, lambda evt, idx=i: self.update_choice(evt, idx))
            self.dropdowns.append(dropdown)

            hbox.Add(dropdown, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
            vbox.Add(hbox, 0, wx.EXPAND | wx.ALL, 5)

        # 确认和取消按钮
        btn_hbox = wx.BoxSizer(wx.HORIZONTAL)
        btn_ok = wx.Button(self, label="确认")
        btn_ok.Bind(wx.EVT_BUTTON, self.on_ok)
        btn_hbox.Add(btn_ok, 0, wx.RIGHT, 10)

        btn_cancel = wx.Button(self, label="取消")
        btn_cancel.Bind(wx.EVT_BUTTON, self.on_cancel)
        btn_hbox.Add(btn_cancel, 0)

        # 将按钮放到整体布局中
        main_vbox = wx.BoxSizer(wx.VERTICAL)
        scrolled_panel.SetSizer(vbox)
        main_vbox.Add(scrolled_panel, 1, wx.EXPAND | wx.ALL, 5)
        main_vbox.Add(btn_hbox, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(main_vbox)
        self.Centre()

    def update_choice(self, event, index):
        """
        更新选择记录
        """
        dropdown = event.GetEventObject()
        self.scene_choices[index] = dropdown.GetString(dropdown.GetSelection())

    def on_ok(self, event):
        """
        确认选择
        """
        self.EndModal(wx.ID_OK)

    def on_cancel(self, event):
        """
        取消选择
        """
        self.EndModal(wx.ID_CANCEL)