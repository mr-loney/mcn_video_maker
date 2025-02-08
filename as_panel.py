import wx
import wx.lib.scrolledpanel as scrolled
import threading
import time
import os
import random
import string
import shutil
import json

class AdvancedSettingsPanel(wx.Dialog):
    """高级设置面板"""
    def __init__(self, parent, config_path):
        super().__init__(parent, title="高级设置", size=(600, 650), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.config_path = config_path
        self.settings = self.load_config()

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 添加帮助文案
        help_text = (
            "帮助:\n"
            "1.图片命名为 _keepimg: 不会用这张图生成视频 (如: img1_keepimg.jpg)\n"
            "2.图片命名为 _start, _center, _end: 生成视频时作为开始帧, 中间帧, 结尾帧 (如: img1_start.jpg)\n"
            "3.视频命名为 _v2v: 会用这个视频进行转绘 (如: video1_v2v.mp4)\n"
            "4.模版文件夹命名为 [媒体账号]folder: 配置中账号会默认绑定到这个媒体账号 (如: [eden]folder)\n"
            "5.如果要复制或停止执行中的模版,删除其文件夹中的run.json,可以重新变为未提交状态\n"
            "6.浮窗文件夹_pop中如果不想被自动绿幕转换文件,就用green_开头命名文件\n"
            "7.文件夹状态为15秒刷新一次,如果想立即看到最新状态可以点击刷新按钮\n"
        )
        help_label = wx.StaticText(panel, label=help_text)
        help_label.Wrap(780)  # 设置自动换行
        main_sizer.Add(help_label, flag=wx.EXPAND | wx.ALL, border=10)

        # 滚动区域
        self.scroll_panel = wx.ScrolledWindow(panel, style=wx.VSCROLL | wx.ALWAYS_SHOW_SB)
        self.scroll_panel.SetScrollRate(10, 10)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        # ============ 在最上方添加两个输入框：指纹浏览器ID、订阅URL ============

        # 指纹浏览器ID
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="指纹浏览器ID:"), flag=wx.ALL, border=5)
        self.browser_id_input = wx.TextCtrl(
            self.scroll_panel, 
            value=self.settings.get("browser_id", "")
        )
        scroll_sizer.Add(self.browser_id_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 订阅URL
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="订阅URL(目前只支持youtube):"), flag=wx.ALL, border=5)
        self.sub_link_input = wx.TextCtrl(
            self.scroll_panel, 
            value=self.settings.get("sub_link", "")
        )
        scroll_sizer.Add(self.sub_link_input, flag=wx.EXPAND | wx.ALL, border=5)

        # Clash配置名
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="Clash配置名:"), flag=wx.ALL, border=5)
        self.clash_id_input = wx.TextCtrl(
            self.scroll_panel, 
            value=self.settings.get("clash_id", "")
        )
        scroll_sizer.Add(self.clash_id_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 是否预约发布
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="是否预约发布:"), flag=wx.ALL, border=5)
        self.is_pre_input = wx.TextCtrl(
            self.scroll_panel, 
            value=self.settings.get("is_pre", "否")
        )
        scroll_sizer.Add(self.is_pre_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 发布到 TikTok 的标题
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="发布到 TikTok 的标题:"), flag=wx.ALL, border=5)
        self.tiktok_title_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("tiktok_title", "Really wonderful!"))
        scroll_sizer.Add(self.tiktok_title_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 发布到 TikTok 的 Tag
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="发布到 TikTok 的 Tag:"), flag=wx.ALL, border=5)
        self.tiktok_tags_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("tiktok_tags", "#foryou #fyp #tiktok #tiktokmademebuyit #viral #hot"))
        scroll_sizer.Add(self.tiktok_tags_input, flag=wx.EXPAND | wx.ALL, border=5)

        # TikTok 的 @
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="发布到 TikTok 的 @:"), flag=wx.ALL, border=5)
        self.tiktok_at_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("tiktok_at", ""))
        scroll_sizer.Add(self.tiktok_at_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 首条评论
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="首条评论:"), flag=wx.ALL, border=5)
        self.first_comment_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("first_comment", ""))
        scroll_sizer.Add(self.first_comment_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 橱窗商品
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="橱窗商品:"), flag=wx.ALL, border=5)
        self.window_product_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("window_product", ""))
        scroll_sizer.Add(self.window_product_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 音乐名
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="音乐名:"), flag=wx.ALL, border=5)
        self.music_name_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("music_name", ""))
        scroll_sizer.Add(self.music_name_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 音乐序号
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="音乐序号:"), flag=wx.ALL, border=5)
        self.music_index_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("music_index", ""))
        scroll_sizer.Add(self.music_index_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 音乐音量
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="音乐音量 (0-1):"), flag=wx.ALL, border=5)
        self.music_volume_input = wx.TextCtrl(self.scroll_panel, value=str(self.settings.get("music_volume", 0)))
        scroll_sizer.Add(self.music_volume_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 原音音量
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="原音音量 (0-1):"), flag=wx.ALL, border=5)
        self.original_volume_input = wx.TextCtrl(self.scroll_panel, value=str(self.settings.get("original_volume", 1)))
        scroll_sizer.Add(self.original_volume_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 发布时间
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="发布时间:"), flag=wx.ALL, border=5)
        self.publish_time_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("publish_time", "4:00,10:00,18:00"))
        scroll_sizer.Add(self.publish_time_input, flag=wx.EXPAND | wx.ALL, border=5)
        
        # 是否重发高播放量视频
        self.repost_checkbox = wx.CheckBox(self.scroll_panel, label="是否重发高播放量视频")
        self.repost_checkbox.SetValue(self.settings.get("repost_high_views", False))
        scroll_sizer.Add(self.repost_checkbox, flag=wx.ALL, border=5)

        # 重发判定播放量
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="重发判定播放量:"), flag=wx.ALL, border=5)
        self.repost_views_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("repost_views_threshold", ""))
        scroll_sizer.Add(self.repost_views_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 是否使用匿名账号
        self.anonymous_checkbox = wx.CheckBox(self.scroll_panel, label="是否使用匿名账号")
        self.anonymous_checkbox.SetValue(self.settings.get("use_anonymous", True))
        scroll_sizer.Add(self.anonymous_checkbox, flag=wx.ALL, border=5)

        # 社媒账号
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="社媒账号:"), flag=wx.ALL, border=5)
        self.social_account_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("social_account", "ghost_0001"))
        self.social_account_input.Bind(wx.EVT_TEXT, self.update_matrix_template)  # 绑定事件
        scroll_sizer.Add(self.social_account_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 添加到的矩阵（不可选输入框）
        scroll_sizer.Add(wx.StaticText(self.scroll_panel, label="添加到的矩阵:"), flag=wx.ALL, border=5)
        self.matrix_template_input = wx.TextCtrl(
            self.scroll_panel,
            value=f"{self.settings.get('social_account', 'ghost_0001')}的矩阵模版",
            style=wx.TE_READONLY
        )
        scroll_sizer.Add(self.matrix_template_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 是否添加为新模版
        self.new_template_checkbox = wx.CheckBox(self.scroll_panel, label="是否添加为新模版")
        self.new_template_checkbox.SetValue(self.settings.get("is_new_template", True))
        scroll_sizer.Add(self.new_template_checkbox, flag=wx.ALL, border=5)

        self.scroll_panel.SetSizer(scroll_sizer)
        scroll_sizer.Fit(self.scroll_panel)
        
        # 是否选择封面
        self.cover_checkbox = wx.CheckBox(self.scroll_panel, label="发布时是否选择封面")
        self.cover_checkbox.SetValue("transmission" in self.settings)
        self.cover_checkbox.Bind(wx.EVT_CHECKBOX, self.toggle_cover_options)
        scroll_sizer.Add(self.cover_checkbox, flag=wx.ALL, border=5)

        # 封面选项容器
        self.cover_options_sizer = wx.BoxSizer(wx.VERTICAL)
        self.c_ratio_input = wx.TextCtrl(self.scroll_panel, value=str(self.settings.get("transmission", {}).get("c_ratio", 0.0)))
        self.f_name_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("transmission", {}).get("f_name", "Emblem"))
        self.f_text_input = wx.TextCtrl(self.scroll_panel, value=", ".join(self.settings.get("transmission", {}).get("f_text", ["Amazing moments.", "Very shocking."])))

        self.cover_options_sizer.Add(wx.StaticText(self.scroll_panel, label="封面选择百分比 (0.0-1.0):"), flag=wx.ALL, border=5)
        self.cover_options_sizer.Add(self.c_ratio_input, flag=wx.EXPAND | wx.ALL, border=5)
        self.cover_options_sizer.Add(wx.StaticText(self.scroll_panel, label="封面贴纸名称:"), flag=wx.ALL, border=5)
        self.cover_options_sizer.Add(self.f_name_input, flag=wx.EXPAND | wx.ALL, border=5)
        self.cover_options_sizer.Add(wx.StaticText(self.scroll_panel, label="封面随机文字 (逗号分隔):"), flag=wx.ALL, border=5)
        self.cover_options_sizer.Add(self.f_text_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 默认隐藏封面选项
        if not self.cover_checkbox.IsChecked():
            self.cover_options_sizer.ShowItems(False)
        scroll_sizer.Add(self.cover_options_sizer, flag=wx.EXPAND)

        self.scroll_panel.SetSizer(scroll_sizer)
        scroll_sizer.Fit(self.scroll_panel)

        # 是否显示字幕
        self.subtitle_checkbox = wx.CheckBox(self.scroll_panel, label="是否显示字幕")
        self.subtitle_checkbox.SetValue("use_tiktok_subtitle" in self.settings)
        self.subtitle_checkbox.Bind(wx.EVT_CHECKBOX, self.toggle_subtitle_options)
        scroll_sizer.Add(self.subtitle_checkbox, flag=wx.ALL, border=5)

        # 字幕选项容器
        self.subtitle_options_sizer = wx.BoxSizer(wx.VERTICAL)

        # 字幕语言
        self.subtitle_language_input = wx.TextCtrl(self.scroll_panel, value=self.settings.get("use_tiktok_subtitle", {}).get("language", "英语"))
        self.subtitle_options_sizer.Add(wx.StaticText(self.scroll_panel, label="字幕语言:"), flag=wx.ALL, border=5)
        self.subtitle_options_sizer.Add(self.subtitle_language_input, flag=wx.EXPAND | wx.ALL, border=5)

        # 字幕类型选择
        self.subtitle_type_choice = wx.Choice(self.scroll_panel, choices=["歌词", "字幕"])
        self.subtitle_type_choice.SetSelection(0 if self.settings.get("use_tiktok_subtitle", {}).get("type") == "lyrics" else 1)
        self.subtitle_options_sizer.Add(wx.StaticText(self.scroll_panel, label="字幕类型:"), flag=wx.ALL, border=5)
        self.subtitle_options_sizer.Add(self.subtitle_type_choice, flag=wx.EXPAND | wx.ALL, border=5)

        # 默认隐藏字幕选项
        if not self.subtitle_checkbox.IsChecked():
            self.subtitle_options_sizer.ShowItems(False)
        scroll_sizer.Add(self.subtitle_options_sizer, flag=wx.EXPAND)

        self.scroll_panel.SetSizer(scroll_sizer)
        scroll_sizer.Fit(self.scroll_panel)

        # 底部按钮
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        save_button = wx.Button(panel, label="确定")
        cancel_button = wx.Button(panel, label="取消")
        button_sizer.AddStretchSpacer()
        button_sizer.Add(save_button, flag=wx.ALL, border=5)
        button_sizer.Add(cancel_button, flag=wx.ALL, border=5)

        # 主布局
        main_sizer.Add(self.scroll_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        main_sizer.Add(button_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        panel.SetSizer(main_sizer)

        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)

        self.CentreOnParent()
    
    def update_matrix_template(self, event):
        """根据社媒账号输入更新矩阵模板"""
        social_account = self.social_account_input.GetValue().strip()
        if social_account:
            self.matrix_template_input.SetValue(f"{social_account}的矩阵模版")
        else:
            self.matrix_template_input.SetValue("未定义的矩阵模版")
    
    def toggle_subtitle_options(self, event):
        """切换字幕选项显示"""
        is_checked = self.subtitle_checkbox.IsChecked()
        self.subtitle_options_sizer.ShowItems(is_checked)
        self.scroll_panel.Layout()  # 重新布局滚动区域
        self.scroll_panel.FitInside()  # 调整滚动条
    
    def toggle_cover_options(self, event):
        """切换封面选项显示"""
        is_checked = self.cover_checkbox.IsChecked()
        self.cover_options_sizer.ShowItems(is_checked)
        self.scroll_panel.Layout()
        self.scroll_panel.FitInside()  # 调整滚动条
    
    def load_config(self):
        """加载配置"""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as file:
                return json.load(file)
        return {}

    def save_config(self):
        """保存配置"""
        # ============== 先保存我们的2个新字段 ==============
        self.settings["browser_id"] = self.browser_id_input.GetValue().strip()
        self.settings["sub_link"] = self.sub_link_input.GetValue().strip()
        self.settings["clash_id"] = self.clash_id_input.GetValue().strip()
        self.settings["is_pre"] = self.is_pre_input.GetValue().strip()

        # ============== 再保存原有字段 ==============
        self.settings["use_anonymous"] = self.anonymous_checkbox.GetValue()
        self.settings["social_account"] = self.social_account_input.GetValue()
        self.settings["matrix_template"] =  self.matrix_template_input.GetValue()
        self.settings["is_new_template"] = self.new_template_checkbox.GetValue()
        self.settings["tiktok_title"] = self.tiktok_title_input.GetValue()
        self.settings["tiktok_tags"] = self.tiktok_tags_input.GetValue()
        self.settings["tiktok_at"] = self.tiktok_at_input.GetValue()
        self.settings["first_comment"] = self.first_comment_input.GetValue()
        self.settings["window_product"] = self.window_product_input.GetValue()
        self.settings["music_name"] = self.music_name_input.GetValue()
        self.settings["music_index"] = self.music_index_input.GetValue()
        self.settings["music_volume"] = float(self.music_volume_input.GetValue())
        self.settings["original_volume"] = float(self.original_volume_input.GetValue())
        self.settings["publish_time"] = self.publish_time_input.GetValue()
        self.settings["repost_high_views"] = self.repost_checkbox.GetValue()
        self.settings["repost_views_threshold"] = self.repost_views_input.GetValue()

        if self.cover_checkbox.IsChecked():
            self.settings["transmission"] = {
                "c_ratio": float(self.c_ratio_input.GetValue()),
                "f_name": self.f_name_input.GetValue(),
                "f_text": [text.strip() for text in self.f_text_input.GetValue().split(",")]
            }
        elif "transmission" in self.settings:
            del self.settings["transmission"]

        # 字幕配置
        if self.subtitle_checkbox.IsChecked():
            subtitle_type = "lyrics" if self.subtitle_type_choice.GetSelection() == 0 else "normal"
            captions_template = (
                ["歌词滚动__", "粉白恋歌__", "复古涂鸦__", "长句emoji__", "多行排版__"]
                if subtitle_type == "lyrics"
                else ["摇晃发光 黄__", "emoji-逐词变色双行__", "新_多行发光粉__", "弹簧-粉__", "emoji 多色发光__"]
            )
            captions_position = 2 if subtitle_type == "lyrics" else -1
            self.settings["use_tiktok_subtitle"] = {
                "type": subtitle_type,
                "captionsTemplateName": captions_template,
                "captionsPosition": captions_position,
                "captionsFontSize": 10,
                "language": self.subtitle_language_input.GetValue()
            }
        elif "use_tiktok_subtitle" in self.settings:
            del self.settings["use_tiktok_subtitle"]

        with open(self.config_path, "w", encoding="utf-8") as file:
            json.dump(self.settings, file, indent=4, ensure_ascii=False)

    def on_save(self, event):
        self.save_config()
        self.Close()

    def on_cancel(self, event):
        self.Close()