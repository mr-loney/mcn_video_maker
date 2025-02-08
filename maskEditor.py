import wx
import os
import random
import string

class MaskEditorFrame(wx.Dialog):
    def __init__(self, parent, image_path):
        super().__init__(parent, title="编辑遮罩",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.parent = parent
        self.image_path = image_path
        self.mask_path = None

        # 打开原图，获取尺寸
        img = wx.Image(image_path, wx.BITMAP_TYPE_ANY)
        self.original_w = img.GetWidth()
        self.original_h = img.GetHeight()

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # 根据原图大小 & 额外UI，算出一个大概的 display_size
        # 如果希望按照原图的大小自适应，则可以让 MaskCanvas 自己决定
        display_size = (min(self.original_w, 800),  # 以 800 为最大宽
                        min(self.original_h, 600))  # 600 为最大高

        self.canvas = MaskCanvas(panel, image_path, self.original_w, self.original_h, display_size)
        vbox.Add(self.canvas, 1, wx.EXPAND|wx.ALL, 5)

        # --- 在底部添加一个 “笔刷大小” label + 滑块 ---
        brush_sizer = wx.BoxSizer(wx.HORIZONTAL)
        brush_sizer.Add(wx.StaticText(panel, label="笔刷大小:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.slider_brush = wx.Slider(panel, value=100, minValue=10, maxValue=200)
        brush_sizer.Add(self.slider_brush, 1, wx.EXPAND | wx.ALL, 5)
        new_size = self.slider_brush.GetValue()
        self.canvas.pen_size = new_size

        # 绑定事件
        self.slider_brush.Bind(wx.EVT_SLIDER, self.on_change_brush)

        vbox.Add(brush_sizer, 0, wx.EXPAND | wx.ALL, 5)
        # -------------------------------------------

        # 确定、取消按钮
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # --- 新增：反色按钮 ---
        invert_btn = wx.Button(panel, label="反色", size=(60, -1))

        # 2) 橡皮擦/笔刷 按钮
        #  初始: is_eraser=False => 按钮文本写 "橡皮擦"
        self.eraser_btn = wx.Button(panel, label="橡皮擦", size=(60, -1))
        self.eraser_btn.Bind(wx.EVT_BUTTON, self.on_toggle_eraser)

        ok_btn = wx.Button(panel, label="确定", size=(60, -1))
        cancel_btn = wx.Button(panel, label="取消", size=(60, -1))

        btn_sizer.AddStretchSpacer()
        # --- 新增：将反色按钮也添加到布局 ---
        btn_sizer.Add(invert_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.eraser_btn, 0, wx.ALL, 5)
        btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
        btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        
        vbox.Add(btn_sizer, 0, wx.EXPAND|wx.ALL, 5)

        ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
        cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        # --- 新增：绑定 反色 按钮事件 ---
        invert_btn.Bind(wx.EVT_BUTTON, self.on_invert_clicked)

        panel.SetSizer(vbox)

        # 让 sizer 计算最小尺寸并适配窗口
        vbox.Fit(self)               # 让窗口适配所需大小
        vbox.SetSizeHints(self)      # 防止窗口被拉到比最小尺寸更小
        self.CentreOnParent()

        # 默认画笔为黑(笔刷)
        self.canvas.is_eraser = False

    def on_toggle_eraser(self, event):
        # 如果当前是 eraser => 切回笔刷
        # 否则 => 切到 eraser
        if self.canvas.is_eraser:
            # 切到笔刷
            self.canvas.is_eraser = False
            self.eraser_btn.SetLabel("橡皮擦")
        else:
            # 切到橡皮擦
            self.canvas.is_eraser = True
            self.eraser_btn.SetLabel("笔刷")
    
    def on_invert_clicked(self, event):
        # 调用画布方法，反转 mask
        self.canvas.invert_mask()
        # 刷新画布显示
        self.canvas.Refresh()

    def on_change_brush(self, event):
        new_size = self.slider_brush.GetValue()
        self.canvas.pen_size = new_size
        
    def on_ok(self, event):
        suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        base, ext = os.path.splitext(self.image_path)
        ext_lower = ext.lower()

        # 决定新的后缀 & wxPython 保存类型
        if ext_lower in [".jpg", ".jpeg"]:
            new_ext = ext_lower  # 保持 .jpg / .jpeg
            wxtype = wx.BITMAP_TYPE_JPEG
        elif ext_lower == ".webp":
            # wxPython原生通常不支持保存webp
            # 如果强行同名：new_ext = ".webp"
            # wxtype = ??? 
            # 这里示例 fallback => .png
            new_ext = ".png"
            wxtype = wx.BITMAP_TYPE_PNG
        else:
            new_ext = ".png"
            wxtype = wx.BITMAP_TYPE_PNG

        # 构造新文件名
        mask_path = f"{base}_mask_{suffix}{new_ext}"

        # 调用画布方法，反转 mask
        self.canvas.invert_mask()
        # 刷新画布显示
        self.canvas.Refresh()

        # 保存
        self.canvas.save_mask_as_bw(mask_path, wxtype)
        self.mask_path = mask_path
        self.EndModal(wx.ID_OK)

    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)


class MaskCanvas(wx.Panel):
    """
    - self.original_img: 用于显示底图(缩放后)
    - self.mask_bmp: 32位 带Alpha的位图(与原图同尺寸)
        其中 alpha=0 表示“透明”(未画部分),
             alpha=255+RGB=黑 表示画的笔迹
    - 绘制时: 
      1) 缩放 original_img 画在底
      2) 缩放 mask_bmp 画在上(Alpha=0 =>看见底图, Alpha=255 =>黑笔)
    - 保存时: 将 mask_bmp 的 alpha>128 =>黑, 否则=>白, 生成纯黑白图
    """

    def __init__(self, parent, original_img_path, original_w, original_h, display_size=(800,600)):
        super().__init__(parent)
        self.original_path = original_img_path

        # 原图(仅做显示参考)
        self.original_img = wx.Image(original_img_path, wx.BITMAP_TYPE_ANY)
        self.original_w = original_w
        self.original_h = original_h

        # 创建 32位带Alpha的位图
        self.mask_bmp = wx.Bitmap(original_w, original_h, 32)
        self.clear_mask_alpha()

        # 计算等比缩放后的显示区域
        self.display_w, self.display_h = display_size
        ratio_w = self.display_w / float(original_w)
        ratio_h = self.display_h / float(original_h)
        self.scale = min(ratio_w, ratio_h)  # 保持等比
        self.view_w = int(original_w * self.scale)
        self.view_h = int(original_h * self.scale)

        self.SetMinSize((self.view_w, self.view_h))

        self.pen_size = 10
        self.is_drawing = False

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_PAINT, self.on_paint)

        # 绑定 size
        self.Bind(wx.EVT_SIZE, self.on_size)

    def invert_mask(self):
        """
        将 alpha=255(黑) -> alpha=0(白)，
        将 alpha=0(白)   -> alpha=255(黑)。
        """
        mask_img = self.mask_bmp.ConvertToImage()
        w, h = mask_img.GetWidth(), mask_img.GetHeight()
        for x in range(w):
            for y in range(h):
                a = mask_img.GetAlpha(x, y)
                if a > 128:
                    # 原先是“黑”，现在变“白”（alpha=0）
                    mask_img.SetAlpha(x, y, 0)
                else:
                    # 原先是“白”，现在变“黑”（alpha=255）
                    mask_img.SetAlpha(x, y, 255)
        self.mask_bmp = wx.Bitmap(mask_img)

    def on_size(self, event):
        event.Skip()  # 先让 sizer 处理

        new_size = self.GetClientSize()
        view_w, view_h = new_size.GetWidth(), new_size.GetHeight()
        ratio_w = view_w / float(self.original_w)
        ratio_h = view_h / float(self.original_h)
        self.scale = min(ratio_w, ratio_h) if (ratio_w>0 and ratio_h>0) else 1.0
        self.Refresh()

    def clear_mask_alpha(self):
        """
        将mask_bmp全部设为alpha=0(透明)
        """
        # 先转成 image
        w, h = self.original_w, self.original_h
        blank_img = wx.Image(w, h, clear=True)  # 24位空图
        blank_img.InitAlpha()
        for x in range(w):
            for y in range(h):
                blank_img.SetAlpha(x, y, 0)  # alpha=0 =>透明
                blank_img.SetRGB(x, y, 0, 0, 0)  # RGB=0,0,0
        self.mask_bmp = wx.Bitmap(blank_img)

    def on_left_down(self, event):
        self.is_drawing = True
        self.draw_point(event.GetPosition())
        self.CaptureMouse()

    def on_left_up(self, event):
        if self.is_drawing:
            self.is_drawing = False
            if self.HasCapture():
                self.ReleaseMouse()

    def on_motion(self, event):
        if self.is_drawing and event.Dragging() and event.LeftIsDown():
            self.draw_point(event.GetPosition())

    def on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        view_w, view_h = self.GetClientSize()

        # (1) 画原图(缩放)
        scaled_orig = self.original_img.Scale(
            int(self.original_w*self.scale),
            int(self.original_h*self.scale),
            wx.IMAGE_QUALITY_HIGH
        )
        dc.DrawBitmap(scaled_orig.ConvertToBitmap(), 0, 0, False)

        # (2) 画mask(带Alpha)
        mask_img = self.mask_bmp.ConvertToImage()
        scaled_mask = mask_img.Scale(
            int(self.original_w*self.scale),
            int(self.original_h*self.scale),
            wx.IMAGE_QUALITY_HIGH
        )
        # useMask=True => alpha=0 区域不覆盖原图
        dc.DrawBitmap(scaled_mask.ConvertToBitmap(), 0, 0, True)

    def draw_point(self, pos):
        """
        在 (pos) 附近画一个圆：
        - 如果是笔刷 => alpha=255（黑）
        - 如果是橡皮擦 => alpha=0（擦掉黑色）
        """
        dx, dy = pos
        mx = int(dx / self.scale)
        my = int(dy / self.scale)

        if 0 <= mx < self.original_w and 0 <= my < self.original_h:
            # 1) 把 mask_bmp 转成 wx.Image
            mask_img = self.mask_bmp.ConvertToImage()

            # 2) 在这个 mask_img 的 (mx, my) 半径 self.pen_size 内做像素修改
            if self.is_eraser:
                new_alpha = 0   # 橡皮擦 -> 白(transparent)
            else:
                new_alpha = 255 # 笔刷 -> 黑

            self.draw_circle_on_image(mask_img, mx, my, self.pen_size, new_alpha)

            # 3) 转回 mask_bmp
            self.mask_bmp = wx.Bitmap(mask_img)

            # 4) 部分刷新
            disp_radius = int(self.pen_size * self.scale) + 2
            update_rect = wx.Rect(dx - disp_radius, dy - disp_radius,
                                disp_radius*2, disp_radius*2)
            self.RefreshRect(update_rect, eraseBackground=False)
    
    def draw_circle_on_image(self, mask_img, cx, cy, radius, alpha_value):
        """
        在 mask_img 上，以(cx,cy)为圆心、radius为半径，
        将区域内所有像素的 alpha 设置为 alpha_value（0或255）。
        """
        w, h = mask_img.GetWidth(), mask_img.GetHeight()
        # 简单地逐像素判断 (x - cx)^2 + (y - cy)^2 <= radius^2
        r_sq = radius * radius
        for x in range(max(cx - radius, 0), min(cx + radius, w - 1) + 1):
            dx = x - cx
            dx_sq = dx * dx
            for y in range(max(cy - radius, 0), min(cy + radius, h - 1) + 1):
                dy = y - cy
                if dx_sq + dy*dy <= r_sq:
                    # 在圆内部
                    mask_img.SetAlpha(x, y, alpha_value)
        # 不用改 RGB，保持为 0,0,0 即可(黑), or 0,0,0 with alpha=0 =>显示白

    def save_mask_as_bw(self, path, wxtype=wx.BITMAP_TYPE_PNG):
        """
        将 self.mask_bmp(带Alpha) 转换为 纯黑白(全尺寸)图:
        alpha>128 => black
        alpha<=128 => white
        然后保存到 path, 并使用 wxtype 作为保存格式(若支持).
        """
        mask_img = self.mask_bmp.ConvertToImage()
        w, h = mask_img.GetWidth(), mask_img.GetHeight()
        out_img = wx.Image(w, h)
        out_img.Clear(255)  # 全白

        for x in range(w):
            for y in range(h):
                a = mask_img.GetAlpha(x,y)
                if a > 128:
                    out_img.SetRGB(x,y,0,0,0)  # black
                else:
                    out_img.SetRGB(x,y,255,255,255)  # white

        # 如果 wx 不支持 webp，写 webp 会报错. 
        out_img.SaveFile(path, wxtype)