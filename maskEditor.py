import wx
import os
import random
import string
import time

class MaskEditorFrame(wx.Dialog):
    def __init__(self, parent, image_path):
        super().__init__(parent, title="编辑遮罩", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.parent = parent
        self.image_path = image_path
        self.mask_path = None

        # 打开原图，获取尺寸
        img = wx.Image(image_path, wx.BITMAP_TYPE_ANY)
        self.original_w = img.GetWidth()
        self.original_h = img.GetHeight()

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 根据原图大小设定画布大小 (最大 800x600)
        display_size = (min(self.original_w, 800),
                        min(self.original_h, 600))

        self.canvas = MaskCanvas(panel, image_path, self.original_w, self.original_h, display_size)
        vbox.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 5)

        # 笔刷大小
        brush_sizer = wx.BoxSizer(wx.HORIZONTAL)
        brush_sizer.Add(wx.StaticText(panel, label="笔刷大小:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.slider_brush = wx.Slider(panel, value=50, minValue=5, maxValue=300)
        brush_sizer.Add(self.slider_brush, 1, wx.EXPAND | wx.ALL, 5)
        self.slider_brush.Bind(wx.EVT_SLIDER, self.on_change_brush)
        self.canvas.pen_size = self.slider_brush.GetValue()
        vbox.Add(brush_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # 底部按钮
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        invert_btn = wx.Button(panel, label="反色")
        invert_btn.Bind(wx.EVT_BUTTON, self.on_invert_clicked)

        self.eraser_btn = wx.Button(panel, label="橡皮擦")
        self.eraser_btn.Bind(wx.EVT_BUTTON, self.on_toggle_eraser)

        ok_btn = wx.Button(panel, label="确定")
        ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)

        cancel_btn = wx.Button(panel, label="取消")
        cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)

        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(invert_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.eraser_btn, 0, wx.ALL, 5)
        btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
        btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(vbox)
        vbox.Fit(self)
        vbox.SetSizeHints(self)
        self.CentreOnParent()

        # 默认笔刷模式
        self.canvas.is_eraser = False

    def on_change_brush(self, event):
        new_size = self.slider_brush.GetValue()
        self.canvas.pen_size = new_size
        # 更新
        self.canvas.Refresh(False)  # 全局刷新，不擦背景

    def on_invert_clicked(self, event):
        self.canvas.invert_mask()
        self.canvas.Refresh(False)

    def on_toggle_eraser(self, event):
        if self.canvas.is_eraser:
            self.canvas.is_eraser = False
            self.eraser_btn.SetLabel("橡皮擦")
        else:
            self.canvas.is_eraser = True
            self.eraser_btn.SetLabel("笔刷")

    def on_ok(self, event):
        suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        base, ext = os.path.splitext(self.image_path)
        ext_lower = ext.lower()

        if ext_lower in [".jpg", ".jpeg"]:
            new_ext = ext_lower
            wxtype = wx.BITMAP_TYPE_JPEG
        elif ext_lower == ".webp":
            new_ext = ".png"
            wxtype = wx.BITMAP_TYPE_PNG
        else:
            new_ext = ".png"
            wxtype = wx.BITMAP_TYPE_PNG

        mask_path = f"{base}_mask_{suffix}{new_ext}"

        # 先反转一下演示
        self.canvas.invert_mask()
        self.canvas.Refresh(False)

        self.canvas.save_mask_as_bw(mask_path, wxtype)
        self.mask_path = mask_path
        self.EndModal(wx.ID_OK)

    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)

class MaskCanvas(wx.Panel):
    """
    带“空心圆光标” + 遮罩绘制，避免拖影:
      - 用全局刷新(Refresh) + AutoBufferedPaintDC
      - 自定义空的 EVT_ERASE_BACKGROUND 避免闪烁
    """

    def __init__(self, parent, original_img_path, original_w, original_h, display_size=(800,600)):
        super().__init__(parent)
        self.original_path = original_img_path
        self.original_img = wx.Image(original_img_path, wx.BITMAP_TYPE_ANY)
        self.original_w = original_w
        self.original_h = original_h

        self.mask_bmp = wx.Bitmap(original_w, original_h, 32)
        self.clear_mask_alpha()

        ratio_w = display_size[0] / float(original_w)
        ratio_h = display_size[1] / float(original_h)
        self.scale = min(ratio_w, ratio_h)
        self.view_w = int(original_w * self.scale)
        self.view_h = int(original_h * self.scale)
        self.SetMinSize((self.view_w, self.view_h))

        self.pen_size = 50
        self.is_drawing = False
        self.is_eraser = False

        # 鼠标光标
        self.cursor_x = -1
        self.cursor_y = -1
        self.show_brush_cursor = False

        # 启用双缓冲防止闪烁
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # 事件
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave_window)
        self.Bind(wx.EVT_ENTER_WINDOW, self.on_enter_window)
        self.Bind(wx.EVT_SIZE, self.on_size)
        # 关键: 禁用默认背景擦除 => 避免闪烁
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)

    def on_erase_background(self, event):
        """啥都不做 => 避免重复擦背景造成闪烁"""
        pass

    def on_enter_window(self, event):
        self.SetCursor(wx.Cursor(wx.CURSOR_BLANK))
        self.show_brush_cursor = True
        self.Refresh(False)
        event.Skip()

    def on_leave_window(self, event):
        self.SetCursor(wx.NullCursor)
        self.show_brush_cursor = False
        self.Refresh(False)
        event.Skip()

    def on_size(self, event):
        event.Skip()
        w, h = self.GetClientSize()
        if self.original_w and self.original_h:
            ratio_w = w / float(self.original_w)
            ratio_h = h / float(self.original_h)
            self.scale = min(ratio_w, ratio_h)
        self.Refresh(False)

    def clear_mask_alpha(self):
        w, h = self.original_w, self.original_h
        img = wx.Image(w, h, clear=True)
        img.InitAlpha()
        for x in range(w):
            for y in range(h):
                img.SetAlpha(x, y, 0)
                img.SetRGB(x, y, 0, 0, 0)
        self.mask_bmp = wx.Bitmap(img)

    def invert_mask(self):
        mask_img = self.mask_bmp.ConvertToImage()
        w, h = mask_img.GetWidth(), mask_img.GetHeight()
        for x in range(w):
            for y in range(h):
                a = mask_img.GetAlpha(x, y)
                if a > 128:
                    mask_img.SetAlpha(x, y, 0)
                else:
                    mask_img.SetAlpha(x, y, 255)
        self.mask_bmp = wx.Bitmap(mask_img)

    def on_left_down(self, event):
        self.is_drawing = True
        self.draw_point(event.GetPosition())
        self.CaptureMouse()

        # 全窗口刷新(不擦背景)，避免拖影
        self.Refresh(False)
        event.Skip()

    def on_left_up(self, event):
        if self.is_drawing:
            self.is_drawing = False
            if self.HasCapture():
                self.ReleaseMouse()

    def on_motion(self, event):
        x, y = event.GetPosition()
        self.cursor_x, self.cursor_y = x, y
        # 若在画布内 => show_brush_cursor = True
        if 0 <= x < self.view_w and 0 <= y < self.view_h:
            self.show_brush_cursor = True
        else:
            self.show_brush_cursor = False

        if self.is_drawing and event.LeftIsDown():
            self.draw_point((x, y))

        # 全窗口刷新(不擦背景)，避免拖影
        self.Refresh(False)
        event.Skip()

    def on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        # (1) 画原图
        scaled_orig = self.original_img.Scale(
            int(self.original_w*self.scale),
            int(self.original_h*self.scale),
            wx.IMAGE_QUALITY_HIGH
        )
        dc.DrawBitmap(scaled_orig.ConvertToBitmap(), 0, 0, False)

        # (2) 画 遮罩
        mask_img = self.mask_bmp.ConvertToImage()
        scaled_mask = mask_img.Scale(
            int(self.original_w*self.scale),
            int(self.original_h*self.scale),
            wx.IMAGE_QUALITY_HIGH
        )
        dc.DrawBitmap(scaled_mask.ConvertToBitmap(), 0, 0, True)

        # (3) 画空心圆光标
        if self.show_brush_cursor:
            self.draw_brush_cursor(dc)

    def draw_brush_cursor(self, dc):
        pen = wx.Pen(wx.Colour(255,255,255), 1, wx.PENSTYLE_SOLID)
        dc.SetPen(pen)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        r = self.pen_size // 2
        dc.DrawCircle(self.cursor_x, self.cursor_y, r)

    def draw_point(self, pos):
        # 根据缩放算出 mask 中的坐标
        x, y = pos
        mx = int(x / self.scale)
        my = int(y / self.scale)
        if 0 <= mx < self.original_w and 0 <= my < self.original_h:
            mask_img = self.mask_bmp.ConvertToImage()
            alpha_val = 0 if self.is_eraser else 255
            self.draw_circle_on_image(mask_img, mx, my, self.pen_size, alpha_val)
            self.mask_bmp = wx.Bitmap(mask_img)

    def draw_circle_on_image(self, mask_img, cx, cy, radius, alpha_value):
        w, h = mask_img.GetWidth(), mask_img.GetHeight()
        r_sq = radius * radius
        left = max(cx - radius, 0)
        right = min(cx + radius, w - 1)
        for px in range(left, right+1):
            dx_sq = (px - cx)**2
            for py in range(max(cy - radius, 0), min(cy + radius, h - 1)+1):
                dy = py - cy
                if dx_sq + dy*dy <= r_sq:
                    mask_img.SetAlpha(px, py, alpha_value)

    def save_mask_as_bw(self, path, wxtype=wx.BITMAP_TYPE_PNG):
        mask_img = self.mask_bmp.ConvertToImage()
        w, h = mask_img.GetWidth(), mask_img.GetHeight()
        out_img = wx.Image(w, h)
        out_img.Clear(255)  # 全白
        for x in range(w):
            for y in range(h):
                a = mask_img.GetAlpha(x, y)
                if a > 128:
                    out_img.SetRGB(x, y, 0, 0, 0)
                else:
                    out_img.SetRGB(x, y, 255, 255, 255)
        out_img.SaveFile(path, wxtype)