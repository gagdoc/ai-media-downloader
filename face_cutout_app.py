import os
import sys
import json
import threading
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageGrab
from datetime import datetime
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

from face_cutout_engine import FaceCutoutEngine

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DEFAULT_OUT_DIR = "/Users/gagdox/Documents/ChatGPT/ComfyUI MASTER"
CONFIG_FILE = os.path.expanduser("~/.face_mask_studio_config.json")

def load_saved_output_dir():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                d = data.get("output_dir")
                if d and os.path.isdir(d):
                    return d
        except Exception:
            pass
    return DEFAULT_OUT_DIR

def save_output_dir(dir_path):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"output_dir": dir_path}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save config: {e}")

def make_checkerboard_bg(width, height, grid_size=12):
    img = Image.new("RGB", (width, height), (220, 220, 220))
    draw = ImageDraw.Draw(img)
    color2 = (180, 180, 180)
    for y in range(0, height, grid_size):
        for x in range(0, width, grid_size):
            if (x // grid_size + y // grid_size) % 2 == 1:
                draw.rectangle([x, y, x + grid_size, y + grid_size], fill=color2)
    return img

class FaceCutoutApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Face & Hair Masking Studio (Interactive Canvas)")
        self.geometry("1240x920")
        self.minsize(1050, 780)

        engine_dir = os.path.dirname(os.path.abspath(__file__))
        self.engine = FaceCutoutEngine(model_dir=engine_dir)

        self.current_image_path = None
        self.current_cv_img = None
        self.current_mask = None        # Original resolution mask (uint8 0~255)
        self.current_boxes = []         # List of [x1, y1, x2, y2] in image coordinates
        self.selected_box_idx = -1
        self.current_result_img = None

        self.output_dir = load_saved_output_dir()
        os.makedirs(self.output_dir, exist_ok=True)

        self.is_batch_mode = False
        self.batch_files = []

        # Canvas display scaling
        self.canvas_scale = 1.0
        self.canvas_offset_x = 0
        self.canvas_offset_y = 0
        self.canvas_disp_w = 0
        self.canvas_disp_h = 0

        # Mouse interaction states
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.active_handle = None # 'move', 'nw', 'ne', 'sw', 'se'
        self.is_drawing_new_box = False
        self.temp_box = None

        self._setup_ui()

        # Keyboard shortcuts for clipboard paste
        self.bind_all("<Command-v>", self.paste_clipboard_image)
        self.bind_all("<Control-v>", self.paste_clipboard_image)

    def _setup_ui(self):
        # 1. Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 4))

        title_lbl = ctk.CTkLabel(
            header, 
            text="🎭 Face & Hair Interactive Masking Studio", 
            font=ctk.CTkFont(size=23, weight="bold")
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            header,
            text="AI 자동 감지 + 마우스 드래그 이동/크기조절 및 지우개/브러시 수동 편집 지원",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        sub_lbl.pack(anchor="w")

        # 2. Top File Bar
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=20, pady=2)

        self.btn_select_file = ctk.CTkButton(
            btn_bar, text="📁 이미지 파일 열기", command=self.choose_single_file,
            width=140, height=32, font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_select_file.pack(side="left", padx=(0, 6))

        self.btn_paste = ctk.CTkButton(
            btn_bar, text="📋 붙여넣기 (Cmd+V)", command=self.paste_clipboard_image,
            width=150, height=32, fg_color="#2B6CB0", hover_color="#2C5282", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_paste.pack(side="left", padx=(0, 8))

        self.btn_select_folder = ctk.CTkButton(
            btn_bar, text="📂 폴더 일괄 변환(Batch)", command=self.choose_folder,
            width=160, height=32, fg_color="#4A5568", hover_color="#2D3748", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_select_folder.pack(side="left", padx=4)

        self.lbl_current_file = ctk.CTkLabel(
            btn_bar, text="선택된 파일이 없습니다.", font=ctk.CTkFont(size=12), text_color="gray60"
        )
        self.lbl_current_file.pack(side="left", padx=12)

        # 3. Mode Options Bar
        options_bar = ctk.CTkFrame(self, fg_color="#2D3748", corner_radius=8)
        options_bar.pack(fill="x", padx=20, pady=(3, 4))

        # Target
        c1 = ctk.CTkFrame(options_bar, fg_color="transparent")
        c1.pack(side="left", padx=(10, 8), pady=5)
        ctk.CTkLabel(c1, text="🎯 대상:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 4))
        self.seg_mode = ctk.CTkSegmentedButton(
            c1, values=["얼굴만", "얼굴 + 헤어", "헤어만"], command=self.on_mode_switch,
            font=ctk.CTkFont(size=11), selected_color="#3182CE", selected_hover_color="#2B6CB0"
        )
        self.seg_mode.set("얼굴만")
        self.seg_mode.pack(side="left")

        # Shape
        c2 = ctk.CTkFrame(options_bar, fg_color="transparent")
        c2.pack(side="left", padx=8, pady=5)
        ctk.CTkLabel(c2, text="📐 형태:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 4))
        self.seg_shape = ctk.CTkSegmentedButton(
            c2, values=["정밀 누끼", "단색 박스"], command=self.on_shape_switch,
            font=ctk.CTkFont(size=11), selected_color="#DD6B20", selected_hover_color="#C05621"
        )
        self.seg_shape.set("정밀 누끼")
        self.seg_shape.pack(side="left")

        # Fill
        c3 = ctk.CTkFrame(options_bar, fg_color="transparent")
        c3.pack(side="left", padx=8, pady=5)
        ctk.CTkLabel(c3, text="🎨 채우기:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 4))
        self.seg_fill = ctk.CTkSegmentedButton(
            c3, values=["투명 (Alpha)", "흰색 (White)", "검은색 (Black)"], command=self.on_fill_switch,
            font=ctk.CTkFont(size=11), selected_color="#805AD5", selected_hover_color="#6B46C1"
        )
        self.seg_fill.set("투명 (Alpha)")
        self.seg_fill.pack(side="left")

        # 4. Interactive Editing Toolbar
        edit_toolbar = ctk.CTkFrame(self, fg_color="#1A202C", corner_radius=8)
        edit_toolbar.pack(fill="x", padx=20, pady=(0, 5))

        lbl_tools = ctk.CTkLabel(edit_toolbar, text="🛠️ 수동 편집:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#63B3ED")
        lbl_tools.pack(side="left", padx=(10, 6), pady=4)

        self.seg_tool = ctk.CTkSegmentedButton(
            edit_toolbar,
            values=["🖱️ 박스 이동/크기", "➕ 새 박스 그리기", "🖌️ 브러시(추가)", "🧽 지우개(삭제)"],
            command=self.on_tool_changed,
            font=ctk.CTkFont(size=11, weight="bold"),
            selected_color="#38A169", selected_hover_color="#2F855A"
        )
        self.seg_tool.set("🖱️ 박스 이동/크기")
        self.seg_tool.pack(side="left", padx=4, pady=4)

        # Brush size
        ctk.CTkLabel(edit_toolbar, text="브러시 크기:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(12, 4))
        self.slider_brush_size = ctk.CTkSlider(edit_toolbar, from_=5, to=80, number_of_steps=25, width=90)
        self.slider_brush_size.set(30)
        self.slider_brush_size.pack(side="left", padx=4)

        # Reset buttons
        self.btn_reset_ai = ctk.CTkButton(
            edit_toolbar, text="🤖 AI 다시 감지", width=95, height=26, font=ctk.CTkFont(size=11),
            fg_color="#4A5568", hover_color="#2D3748", command=self.reset_to_ai
        )
        self.btn_reset_ai.pack(side="right", padx=(4, 10), pady=4)

        self.btn_clear_mask = ctk.CTkButton(
            edit_toolbar, text="🗑️ 전체 비우기", width=90, height=26, font=ctk.CTkFont(size=11),
            fg_color="#E53E3E", hover_color="#C53030", command=self.clear_all_mask
        )
        self.btn_clear_mask.pack(side="right", padx=4, pady=4)

        # 5. Center View (Interactive Canvas on Left vs Result Preview on Right)
        center_frame = ctk.CTkFrame(self, corner_radius=10)
        center_frame.pack(fill="both", expand=True, padx=20, pady=4)
        center_frame.columnconfigure((0, 1), weight=1)
        center_frame.rowconfigure(0, weight=1)

        # Left Canvas Box
        left_box = ctk.CTkFrame(center_frame, fg_color="#171923", corner_radius=8)
        left_box.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        lbl_c_title = ctk.CTkLabel(left_box, text="[대화형 편집 캔버스 (마우스로 이동/크기조절/지우기)]", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_c_title.pack(pady=(4, 2))

        # Tkinter Canvas
        self.canvas = tk.Canvas(left_box, bg="#111217", highlightthickness=0, cursor="arrow")
        self.canvas.pack(fill="both", expand=True, padx=6, pady=(2, 6))
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Right Result Box
        right_box = ctk.CTkFrame(center_frame, fg_color="#171923", corner_radius=8)
        right_box.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self.lbl_res_title = ctk.CTkLabel(right_box, text="[최종 결과 실시간 미리보기]", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_res_title.pack(pady=(4, 2))
        self.lbl_preview_res = ctk.CTkLabel(right_box, text="결과가 여기에 표시됩니다", text_color="gray50")
        self.lbl_preview_res.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        # 6. Bottom Sliders & Action Panel
        bottom_panel = ctk.CTkFrame(self, corner_radius=10)
        bottom_panel.pack(fill="x", padx=20, pady=(3, 8))

        sliders_row = ctk.CTkFrame(bottom_panel, fg_color="transparent")
        sliders_row.pack(fill="x", padx=15, pady=6)
        sliders_row.columnconfigure((0, 1, 2), weight=1)

        # Margin
        b1 = ctk.CTkFrame(sliders_row, fg_color="transparent")
        b1.grid(row=0, column=0, sticky="ew", padx=6)
        self.lbl_expand_val = ctk.CTkLabel(b1, text="영역/박스 마진: 0 px", font=ctk.CTkFont(size=11, weight="bold"))
        self.lbl_expand_val.pack(anchor="w")
        self.slider_expand = ctk.CTkSlider(b1, from_=-30, to=120, number_of_steps=75, command=self.on_slider_changed)
        self.slider_expand.set(0)
        self.slider_expand.pack(fill="x", pady=(2, 0))

        # Scale
        b2 = ctk.CTkFrame(sliders_row, fg_color="transparent")
        b2.grid(row=0, column=1, sticky="ew", padx=6)
        self.lbl_scale_val = ctk.CTkLabel(b2, text="윤곽 비율 확장: 1.00x", font=ctk.CTkFont(size=11, weight="bold"))
        self.lbl_scale_val.pack(anchor="w")
        self.slider_scale = ctk.CTkSlider(b2, from_=1.0, to=1.5, number_of_steps=25, command=self.on_slider_changed)
        self.slider_scale.set(1.0)
        self.slider_scale.pack(fill="x", pady=(2, 0))

        # Feather
        b3 = ctk.CTkFrame(sliders_row, fg_color="transparent")
        b3.grid(row=0, column=2, sticky="ew", padx=6)
        self.lbl_feather_val = ctk.CTkLabel(b3, text="경계면 페더링: 5 px", font=ctk.CTkFont(size=11, weight="bold"))
        self.lbl_feather_val.pack(anchor="w")
        self.slider_feather = ctk.CTkSlider(b3, from_=0, to=30, number_of_steps=30, command=self.on_slider_changed)
        self.slider_feather.set(5)
        self.slider_feather.pack(fill="x", pady=(2, 0))

        # Save row
        out_row = ctk.CTkFrame(bottom_panel, fg_color="transparent")
        out_row.pack(fill="x", padx=15, pady=3)
        ctk.CTkLabel(out_row, text="저장 폴더:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 6))
        self.lbl_out_dir = ctk.CTkLabel(out_row, text=self.output_dir, font=ctk.CTkFont(size=11), text_color="#63B3ED", anchor="w")
        self.lbl_out_dir.pack(side="left", fill="x", expand=True)

        btn_ch_dir = ctk.CTkButton(out_row, text="폴더 변경", width=75, height=26, font=ctk.CTkFont(size=11), fg_color="#4A5568", hover_color="#2D3748", command=self.change_output_dir)
        btn_ch_dir.pack(side="right", padx=(6, 0))

        action_row = ctk.CTkFrame(bottom_panel, fg_color="transparent")
        action_row.pack(fill="x", padx=15, pady=(3, 6))
        self.progress_bar = ctk.CTkProgressBar(action_row)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.btn_save_finder = ctk.CTkButton(action_row, text="📂 결과 폴더 열기", width=120, height=34, fg_color="#4A5568", hover_color="#2D3748", command=self.open_output_folder)
        self.btn_save_finder.pack(side="right", padx=4)

        self.btn_run = ctk.CTkButton(action_row, text="✨ 변환 이미지 저장", width=150, height=34, font=ctk.CTkFont(size=12, weight="bold"), fg_color="#3182CE", hover_color="#2B6CB0", command=self.start_process)
        self.btn_run.pack(side="right", padx=4)

        self.status_label = ctk.CTkLabel(self, text="준비 완료", font=ctk.CTkFont(size=11), text_color="gray50")
        self.status_label.pack(side="bottom", anchor="w", padx=25, pady=(0, 3))

    # --- Mode & Param Handlers ---
    def _get_mode_key(self):
        v = self.seg_mode.get()
        if "헤어만" in v: return "hair_only"
        if "얼굴 + 헤어" in v: return "face_hair"
        return "face_only"

    def _get_shape_key(self):
        v = self.seg_shape.get()
        return "box" if "단색 박스" in v else "contour"

    def _get_fill_key(self):
        v = self.seg_fill.get()
        if "흰색" in v: return "white"
        if "검은색" in v: return "black"
        return "transparent"

    def on_mode_switch(self, val=None):
        if self.current_cv_img is not None:
            self.reset_to_ai()

    def on_shape_switch(self, val=None):
        if self.current_cv_img is not None:
            shape = self._get_shape_key()
            if shape == "box":
                # Ensure boxes exist from mask
                self.rebuild_boxes_from_mask()
                self.seg_tool.set("🖱️ 박스 이동/크기")
            self.render_all()

    def on_fill_switch(self, val=None):
        if self.current_cv_img is not None:
            self.render_all()

    def on_tool_changed(self, val=None):
        t = self.seg_tool.get()
        if "지우개" in t or "브러시" in t:
            self.canvas.config(cursor="crosshair")
        else:
            self.canvas.config(cursor="arrow")
        self.draw_canvas()

    def on_slider_changed(self, val=None):
        expand = int(self.slider_expand.get())
        scale = float(self.slider_scale.get())
        feather = int(self.slider_feather.get())
        self.lbl_expand_val.configure(text=f"영역/박스 마진: {expand:+d} px")
        self.lbl_scale_val.configure(text=f"윤곽 비율 확장: {scale:.2f}x")
        self.lbl_feather_val.configure(text=f"경계면 페더링: {feather} px")
        if self.current_cv_img is not None and not self.is_batch_mode:
            # Re-generate from AI with new slider settings
            self.reset_to_ai()

    # --- Image Loading & AI Init ---
    def paste_clipboard_image(self, event=None):
        try:
            clip = ImageGrab.grabclipboard()
            if isinstance(clip, Image.Image):
                rgb = clip.convert("RGB")
                cv_img = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.current_image_path = os.path.join(self.output_dir, f"clipboard_{timestamp}.png")
                self.current_cv_img = cv_img
                self.is_batch_mode = False
                self.btn_run.configure(text="✨ 변환 이미지 저장")
                self.lbl_current_file.configure(text=f"📋 클립보드 이미지 ({cv_img.shape[1]}x{cv_img.shape[0]})")
                self.status_label.configure(text="클립보드 이미지 AI 감지 중...")
                threading.Thread(target=self._run_ai_init, daemon=True).start()
            elif isinstance(clip, list) and len(clip) > 0 and os.path.exists(clip[0]):
                self.load_image(clip[0])
            else:
                if event is None:
                    messagebox.showinfo("알림", "클립보드에 복사된 이미지가 없습니다.\n웹이나 Finder에서 이미지를 복사(Cmd+C)한 후 다시 시도해 주세요.")
                else:
                    self.status_label.configure(text="클립보드에 이미지가 없습니다. (이미지 복사 후 Cmd+V 하세요)")
        except Exception as e:
            messagebox.showerror("오류", f"클립보드 이미지를 읽을 수 없습니다: {str(e)}")

    def choose_single_file(self):
        file_path = filedialog.askopenfilename(
            title="이미지 선택",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.JPG *.PNG")]
        )
        if file_path:
            self.load_image(file_path)

    def choose_folder(self):
        folder = filedialog.askdirectory(title="일괄 처리할 폴더 선택")
        if folder:
            exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')
            files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(exts)]
            if not files:
                messagebox.showwarning("알림", "선택한 폴더에 이미지 파일이 없습니다.")
                return
            self.is_batch_mode = True
            self.batch_files = sorted(files)
            self.lbl_current_file.configure(text=f"폴더 일괄 모드: 총 {len(self.batch_files)}장 선택됨")
            self.btn_run.configure(text=f"🚀 {len(self.batch_files)}장 일괄 변환 시작")
            self.load_image(self.batch_files[0], update_label=False)

    def load_image(self, file_path, update_label=True):
        self.current_image_path = file_path
        if update_label:
            self.is_batch_mode = False
            self.btn_run.configure(text="✨ 변환 이미지 저장")
            self.lbl_current_file.configure(text=os.path.basename(file_path))

        img = cv2.imread(file_path)
        if img is None:
            messagebox.showerror("오류", f"이미지를 열 수 없습니다: {file_path}")
            return
        
        self.current_cv_img = img
        self.status_label.configure(text="AI 감지 중...")
        threading.Thread(target=self._run_ai_init, daemon=True).start()

    def _run_ai_init(self):
        mode = self._get_mode_key()
        shape = self._get_shape_key()
        expand = int(self.slider_expand.get())
        scale = float(self.slider_scale.get())
        feather = int(self.slider_feather.get())

        mask, num_faces = self.engine.create_mask(
            self.current_cv_img, mode=mode, shape=shape,
            expand_pixels=expand, feather_radius=feather, scale_factor=scale
        )
        self.current_mask = mask
        self.current_boxes = self.engine.get_bounding_boxes(mask, padding=0)
        self.selected_box_idx = 0 if len(self.current_boxes) > 0 else -1

        self.after(0, self.render_all)
        self.after(0, lambda: self.status_label.configure(text=f"감지 완료 ({num_faces}개 감지됨)"))

    def reset_to_ai(self):
        if self.current_cv_img is None: return
        self._run_ai_init()

    def clear_all_mask(self):
        if self.current_cv_img is None: return
        h, w = self.current_cv_img.shape[:2]
        self.current_mask = np.zeros((h, w), dtype=np.uint8)
        self.current_boxes = []
        self.selected_box_idx = -1
        self.render_all()
        self.status_label.configure(text="마스크가 모두 비워졌습니다. 원하는 곳을 마우스로 직접 지정하세요.")

    def rebuild_boxes_from_mask(self):
        if self.current_mask is not None:
            self.current_boxes = self.engine.get_bounding_boxes(self.current_mask, padding=0)
            self.selected_box_idx = 0 if len(self.current_boxes) > 0 else -1

    def sync_mask_from_boxes(self):
        """When in box mode, reconstruct current_mask from current_boxes."""
        if self.current_cv_img is None: return
        h, w = self.current_cv_img.shape[:2]
        new_mask = np.zeros((h, w), dtype=np.uint8)
        for b in self.current_boxes:
            x1, y1, x2, y2 = b
            cv2.rectangle(new_mask, (int(x1), int(y1)), (int(x2), int(y2)), 255, -1)
        
        feather = int(self.slider_feather.get())
        if feather > 0:
            ksize = feather * 2 + 1
            new_mask = cv2.GaussianBlur(new_mask, (ksize, ksize), 0)
        self.current_mask = new_mask

    # --- Interactive Canvas Handling ---
    def on_canvas_resize(self, event):
        self.draw_canvas()

    def draw_canvas(self):
        if self.current_cv_img is None:
            return
        
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 10 or ch <= 10:
            return
        
        orig_h, orig_w = self.current_cv_img.shape[:2]
        scale = min(cw / orig_w, ch / orig_h)
        self.canvas_scale = scale
        dw = int(orig_w * scale)
        dh = int(orig_h * scale)
        self.canvas_disp_w = dw
        self.canvas_disp_h = dh
        off_x = (cw - dw) // 2
        off_y = (ch - dh) // 2
        self.canvas_offset_x = off_x
        self.canvas_offset_y = off_y

        # Base image
        resized_img = cv2.resize(self.current_cv_img, (dw, dh), interpolation=cv2.INTER_AREA)
        disp_bgr = resized_img.copy()

        # Overlay mask in translucent red
        if self.current_mask is not None:
            mask_resized = cv2.resize(self.current_mask, (dw, dh), interpolation=cv2.INTER_NEAREST)
            red_overlay = np.zeros_like(disp_bgr)
            red_overlay[:, :] = [0, 0, 230] # Red in BGR
            alpha = (mask_resized.astype(np.float32) / 255.0 * 0.45)[:, :, np.newaxis]
            disp_bgr = (disp_bgr.astype(np.float32) * (1.0 - alpha) + red_overlay.astype(np.float32) * alpha).astype(np.uint8)

        # Convert to PIL and PhotoImage
        pil_img = Image.fromarray(cv2.cvtColor(disp_bgr, cv2.COLOR_BGR2RGB))
        self.canvas_photo = ImageTk.PhotoImage(pil_img)

        self.canvas.delete("all")
        self.canvas.create_image(off_x, off_y, anchor="nw", image=self.canvas_photo)

        # Draw boxes if box shape or move tool
        shape = self._get_shape_key()
        tool = self.seg_tool.get()
        if shape == "box" or "박스" in tool:
            for idx, b in enumerate(self.current_boxes):
                x1 = off_x + int(b[0] * scale)
                y1 = off_y + int(b[1] * scale)
                x2 = off_x + int(b[2] * scale)
                y2 = off_y + int(b[3] * scale)

                is_sel = (idx == self.selected_box_idx)
                outline_color = "#38A169" if is_sel else "#ED8936"
                width = 3 if is_sel else 2
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline_color, width=width, dash=(4, 2) if not is_sel else ())
                
                # Draw corner handles for selected box
                if is_sel:
                    handle_size = 6
                    corners = [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]
                    for cx, cy in corners:
                        self.canvas.create_rectangle(cx - handle_size, cy - handle_size, cx + handle_size, cy + handle_size, fill="#38A169", outline="white")

        # Draw temporary new box being dragged
        if self.temp_box is not None:
            tx1, ty1, tx2, ty2 = self.temp_box
            self.canvas.create_rectangle(tx1, ty1, tx2, ty2, outline="#4299E1", width=2, dash=(3, 3))

    def _canvas_to_img_coords(self, cx, cy):
        if self.canvas_scale <= 0: return (0, 0)
        ix = (cx - self.canvas_offset_x) / self.canvas_scale
        iy = (cy - self.canvas_offset_y) / self.canvas_scale
        orig_h, orig_w = self.current_cv_img.shape[:2]
        ix = max(0, min(orig_w, ix))
        iy = max(0, min(orig_h, iy))
        return int(ix), int(iy)

    def on_canvas_press(self, event):
        if self.current_cv_img is None: return
        tool = self.seg_tool.get()
        self.drag_start_x = event.x
        self.drag_start_y = event.y

        if "박스 이동/크기" in tool:
            # Check if clicked on a corner handle of selected box
            scale = self.canvas_scale
            off_x = self.canvas_offset_x
            off_y = self.canvas_offset_y

            handle_hit = None
            if 0 <= self.selected_box_idx < len(self.current_boxes):
                b = self.current_boxes[self.selected_box_idx]
                x1 = off_x + b[0] * scale
                y1 = off_y + b[1] * scale
                x2 = off_x + b[2] * scale
                y2 = off_y + b[3] * scale
                h_rad = 8
                if abs(event.x - x1) <= h_rad and abs(event.y - y1) <= h_rad: handle_hit = 'nw'
                elif abs(event.x - x2) <= h_rad and abs(event.y - y1) <= h_rad: handle_hit = 'ne'
                elif abs(event.x - x1) <= h_rad and abs(event.y - y2) <= h_rad: handle_hit = 'sw'
                elif abs(event.x - x2) <= h_rad and abs(event.y - y2) <= h_rad: handle_hit = 'se'
                elif x1 <= event.x <= x2 and y1 <= event.y <= y2: handle_hit = 'move'

            if handle_hit:
                self.active_handle = handle_hit
            else:
                # Check if clicked inside any box
                clicked_idx = -1
                for idx, b in enumerate(self.current_boxes):
                    x1 = off_x + b[0] * scale
                    y1 = off_y + b[1] * scale
                    x2 = off_x + b[2] * scale
                    y2 = off_y + b[3] * scale
                    if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                        clicked_idx = idx
                        break
                self.selected_box_idx = clicked_idx
                self.active_handle = 'move' if clicked_idx != -1 else None
            self.draw_canvas()

        elif "새 박스 그리기" in tool:
            self.is_drawing_new_box = True
            self.temp_box = (event.x, event.y, event.x, event.y)
            self.draw_canvas()

        elif "브러시" in tool or "지우개" in tool:
            self._apply_brush(event.x, event.y, is_eraser=("지우개" in tool))

    def on_canvas_drag(self, event):
        if self.current_cv_img is None: return
        tool = self.seg_tool.get()
        scale = self.canvas_scale

        if "박스 이동/크기" in tool and self.active_handle and 0 <= self.selected_box_idx < len(self.current_boxes):
            dx = (event.x - self.drag_start_x) / scale
            dy = (event.y - self.drag_start_y) / scale
            b = list(self.current_boxes[self.selected_box_idx])

            if self.active_handle == 'move':
                b[0] += dx; b[2] += dx
                b[1] += dy; b[3] += dy
            elif self.active_handle == 'nw':
                b[0] += dx; b[1] += dy
            elif self.active_handle == 'ne':
                b[2] += dx; b[1] += dy
            elif self.active_handle == 'sw':
                b[0] += dx; b[3] += dy
            elif self.active_handle == 'se':
                b[2] += dx; b[3] += dy

            # Ensure x1 < x2, y1 < y2
            orig_h, orig_w = self.current_cv_img.shape[:2]
            b[0] = max(0, min(orig_w, b[0]))
            b[2] = max(0, min(orig_w, b[2]))
            b[1] = max(0, min(orig_h, b[1]))
            b[3] = max(0, min(orig_h, b[3]))

            self.current_boxes[self.selected_box_idx] = b
            self.drag_start_x = event.x
            self.drag_start_y = event.y

            self.sync_mask_from_boxes()
            self.draw_canvas()
            self.update_result_preview()

        elif "새 박스 그리기" in tool and self.is_drawing_new_box:
            self.temp_box = (self.drag_start_x, self.drag_start_y, event.x, event.y)
            self.draw_canvas()

        elif "브러시" in tool or "지우개" in tool:
            self._apply_brush(event.x, event.y, is_eraser=("지우개" in tool))

    def on_canvas_release(self, event):
        if self.current_cv_img is None: return
        tool = self.seg_tool.get()

        if "새 박스 그리기" in tool and self.is_drawing_new_box:
            self.is_drawing_new_box = False
            ix1, iy1 = self._canvas_to_img_coords(self.drag_start_x, self.drag_start_y)
            ix2, iy2 = self._canvas_to_img_coords(event.x, event.y)
            x1, x2 = min(ix1, ix2), max(ix1, ix2)
            y1, y2 = min(iy1, iy2), max(iy1, iy2)
            if (x2 - x1) > 10 and (y2 - y1) > 10:
                self.current_boxes.append([x1, y1, x2, y2])
                self.selected_box_idx = len(self.current_boxes) - 1
                self.sync_mask_from_boxes()
                self.seg_shape.set("단색 박스")
            self.temp_box = None
            self.render_all()

        elif "박스 이동/크기" in tool:
            self.active_handle = None
            self.sync_mask_from_boxes()
            self.render_all()

        elif "브러시" in tool or "지우개" in tool:
            self.rebuild_boxes_from_mask()
            self.render_all()

    def _apply_brush(self, cx, cy, is_eraser=False):
        if self.current_mask is None: return
        ix, iy = self._canvas_to_img_coords(cx, cy)
        radius = int(self.slider_brush_size.get() / self.canvas_scale)
        val = 0 if is_eraser else 255
        cv2.circle(self.current_mask, (ix, iy), radius, val, -1)
        self.draw_canvas()
        self.update_result_preview()

    # --- Render Pipeline ---
    def render_all(self):
        self.draw_canvas()
        self.update_result_preview()

    def update_result_preview(self):
        if self.current_cv_img is None or self.current_mask is None: return
        
        fill = self._get_fill_key()
        shape = self._get_shape_key()
        mode = self._get_mode_key()

        # Render result using current_mask
        res = self.engine.apply_fill_to_mask(self.current_cv_img, self.current_mask, fill_type=fill)
        self.current_result_img = res

        # Display preview
        h, w = res.shape[:2]
        scale = min(450.0 / w, 450.0 / h, 1.0)
        tw, th = int(w * scale), int(h * scale)
        small = cv2.resize(res, (tw, th), interpolation=cv2.INTER_AREA)

        if fill == "transparent":
            pil_rgba = Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGRA2RGBA))
            checker = make_checkerboard_bg(tw, th, grid_size=10)
            checker.paste(pil_rgba, (0, 0), mask=pil_rgba.split()[3])
            disp = checker
            self.lbl_res_title.configure(text="[최종 결과 (체커보드 = 투명)]")
        else:
            disp = Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
            f_txt = "흰색 채우기" if fill == "white" else "검은색 채우기"
            self.lbl_res_title.configure(text=f"[최종 결과 ({f_txt})]")

        ctk_res = ctk.CTkImage(light_image=disp, dark_image=disp, size=(tw, th))
        self.lbl_preview_res.configure(image=ctk_res, text="")

    # --- Save Handlers ---
    def change_output_dir(self):
        folder = filedialog.askdirectory(title="기본 저장 폴더 선택", initialdir=self.output_dir)
        if folder:
            self.output_dir = folder
            save_output_dir(folder)
            self.lbl_out_dir.configure(text=self.output_dir)
            self.status_label.configure(text=f"기본 저장 폴더가 저장되었습니다: {folder}")
            messagebox.showinfo("설정 완료", f"기본 저장 폴더가 설정되었습니다!\n다음 앱 실행 시에도 이 폴더가 기본으로 자동 지정됩니다.\n\n경로:\n{folder}")

    def open_output_folder(self):
        if os.path.exists(self.output_dir):
            subprocess.run(["open", self.output_dir])
        else:
            messagebox.showinfo("알림", "저장 폴더가 아직 존재하지 않습니다.")

    def start_process(self):
        if self.is_batch_mode:
            if not self.batch_files:
                messagebox.showwarning("알림", "변환할 파일이 없습니다.")
                return
            threading.Thread(target=self._run_batch, daemon=True).start()
        else:
            if self.current_result_img is None:
                messagebox.showwarning("알림", "먼저 이미지를 선택해 주세요.")
                return
            self._save_single()

    def _save_single(self):
        base_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
        mode = self._get_mode_key()
        shape = self._get_shape_key()
        fill = self._get_fill_key()
        out_name = f"{base_name}_{mode}_{shape}_{fill}_custom.png"
        out_path = os.path.join(self.output_dir, out_name)

        cv2.imwrite(out_path, self.current_result_img)
        self.status_label.configure(text=f"저장 완료: {out_name}")
        messagebox.showinfo("완료", f"성공적으로 저장되었습니다!\n\n파일명:\n{out_name}\n\n위치:\n{out_path}")

    def _run_batch(self):
        total = len(self.batch_files)
        mode = self._get_mode_key()
        shape = self._get_shape_key()
        fill = self._get_fill_key()
        expand = int(self.slider_expand.get())
        scale = float(self.slider_scale.get())
        feather = int(self.slider_feather.get())

        self.btn_run.configure(state="disabled")
        self.btn_select_file.configure(state="disabled")
        self.btn_select_folder.configure(state="disabled")

        success_count = 0
        for idx, fpath in enumerate(self.batch_files):
            try:
                base_name = os.path.splitext(os.path.basename(fpath))[0]
                out_name = f"{base_name}_{mode}_{shape}_{fill}.png"
                out_path = os.path.join(self.output_dir, out_name)
                self.engine.process_file(
                    fpath, out_path, mode=mode, shape=shape, fill_type=fill,
                    expand_pixels=expand, feather_radius=feather, scale_factor=scale
                )
                success_count += 1
            except Exception as e:
                print(f"Error on {fpath}: {e}")

            progress = (idx + 1) / total
            self.after(0, lambda p=progress, i=idx+1: self._update_batch_progress(p, i, total))

        self.after(0, lambda: self._finish_batch(success_count, total))

    def _update_batch_progress(self, progress, current, total):
        self.progress_bar.set(progress)
        self.status_label.configure(text=f"일괄 변환 중... ({current}/{total})")

    def _finish_batch(self, success_count, total):
        self.btn_run.configure(state="normal")
        self.btn_select_file.configure(state="normal")
        self.btn_select_folder.configure(state="normal")
        self.status_label.configure(text=f"일괄 변환 완료! 총 {success_count}/{total}개 저장됨.")
        messagebox.showinfo("일괄 변환 완료", f"총 {total}장 중 {success_count}장 변환 완료!\n\n저장 위치:\n{self.output_dir}")

if __name__ == "__main__":
    app = FaceCutoutApp()
    app.mainloop()
