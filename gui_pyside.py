"""
RVC 实时变声器 - PySide6 界面(纯黑+橙)
阶段 2:最小可运行版 —— 模型下拉/设备选择/开始停止/延迟显示

音频引擎逻辑忠实搬运自 gui_v1.py(FreeSimpleGUI 版),仅将
audio_callback 对 GUI 的更新改为 Qt 信号(跨线程安全)。
"""
import os
import sys
from dotenv import load_dotenv
import shutil

# 无控制台(pythonw.exe)启动时 sys.stdout/stderr 为 None,
# 把日志重定向到文件,避免写日志报错,同时保留排错能力。
if sys.stdout is None or sys.stderr is None:
    try:
        _log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "run.log"
        )
        _log_file = open(_log_path, "w", encoding="utf-8")
        sys.stdout = _log_file
        sys.stderr = _log_file
    except Exception:
        pass

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*weight_norm.*")
warnings.filterwarnings("ignore", message=".*torch.load.*")

load_dotenv()

os.environ["OMP_NUM_THREADS"] = "4"
if sys.platform == "darwin":
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

now_dir = os.getcwd()
sys.path.append(now_dir)
import multiprocessing

flag_vc = False


def printt(strr, *args):
    if len(args) == 0:
        print(strr)
    else:
        print(strr % args)


def phase_vocoder(a, b, fade_out, fade_in):
    window = torch.sqrt(fade_out * fade_in)
    fa = torch.fft.rfft(a * window)
    fb = torch.fft.rfft(b * window)
    absab = torch.abs(fa) + torch.abs(fb)
    n = a.shape[0]
    if n % 2 == 0:
        absab[1:-1] *= 2
    else:
        absab[1:] *= 2
    phia = torch.angle(fa)
    phib = torch.angle(fb)
    deltaphase = phib - phia
    deltaphase = deltaphase - 2 * np.pi * torch.floor(deltaphase / 2 / np.pi + 0.5)
    w = 2 * np.pi * torch.arange(n // 2 + 1).to(a) + deltaphase
    t = torch.arange(n).unsqueeze(-1).to(a) / n
    result = (
        a * (fade_out**2)
        + b * (fade_in**2)
        + torch.sum(absab * torch.cos(w * t + phia), -1) * window / n
    )
    return result


class Harvest(multiprocessing.Process):
    def __init__(self, inp_q, opt_q):
        multiprocessing.Process.__init__(self)
        self.inp_q = inp_q
        self.opt_q = opt_q

    def run(self):
        import numpy as np
        import pyworld

        while 1:
            idx, x, res_f0, n_cpu, ts = self.inp_q.get()
            f0, t = pyworld.harvest(
                x.astype(np.double),
                fs=16000,
                f0_ceil=1100,
                f0_floor=50,
                frame_period=10,
            )
            res_f0[idx] = f0
            if len(res_f0.keys()) >= n_cpu:
                self.opt_q.put(ts)


if __name__ == "__main__":
    import json
    import re
    import threading
    import time
    import traceback
    from multiprocessing import Queue, cpu_count
    from queue import Empty

    # 先导入 PySide6(轻量),立刻建 QApplication + 闪屏,
    # 让用户双击后 1 秒内看到反馈,避免以为启动失败而重复双击。
    from PySide6.QtCore import Qt, Signal, QObject, QThread
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QApplication,
        QWidget,
        QLabel,
        QPushButton,
        QComboBox,
        QVBoxLayout,
        QHBoxLayout,
        QGridLayout,
        QGroupBox,
        QFileDialog,
        QMessageBox,
        QSlider,
        QCheckBox,
        QStackedWidget,
        QSplashScreen,
    )
    from PySide6.QtGui import QPixmap, QColor, QPainter

    app = QApplication(sys.argv)
    # 简易闪屏(纯黑+橙,立即显示)
    _pix = QPixmap(420, 180)
    _pix.fill(QColor("#0d0d0d"))
    _p = QPainter(_pix)
    _p.setPen(QColor("#FF7A18"))
    _f = QFont("Microsoft YaHei")
    _f.setPixelSize(22)
    _f.setBold(True)
    _p.setFont(_f)
    _p.drawText(_pix.rect(), Qt.AlignCenter, "RVC 变声器\n\n正在启动,请稍候…")
    _p.end()
    splash = QSplashScreen(_pix)
    splash.show()
    app.processEvents()

    # 重量级导入(耗时,闪屏已显示,用户不会以为卡死)
    splash.showMessage("正在加载运行库…", Qt.AlignBottom | Qt.AlignHCenter, QColor("#888"))
    app.processEvents()
    import librosa
    from tools.torchgate import TorchGate
    import numpy as np
    import sounddevice as sd
    import torch
    import torch.nn.functional as F
    import torchaudio.transforms as tat

    from infer.lib import rtrvc as rvc_for_realtime
    from i18n.i18n import I18nAuto
    from configs.config import Config

    i18n = I18nAuto()

    inp_q = Queue()
    opt_q = Queue()
    n_cpu = min(cpu_count(), 8)
    harvest_procs = []
    for _ in range(n_cpu):
        p = Harvest(inp_q, opt_q)
        p.daemon = True
        p.start()
        harvest_procs.append(p)

    # ============ 纯黑 + 橙 样式(阶段 4 会进一步细化) ============
    ORANGE = "#FF7A18"
    DARK_QSS = f"""
    QWidget {{
        background-color: #0d0d0d;
        color: #e8e8e8;
        font-family: "Microsoft YaHei", "微软雅黑";
        font-size: 13px;
    }}
    QGroupBox {{
        border: 1px solid #2a2a2a;
        border-radius: 8px;
        margin-top: 12px;
        padding: 10px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 5px;
        color: {ORANGE};
    }}
    QComboBox {{
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 5px;
        padding: 5px 8px;
        min-height: 22px;
    }}
    QComboBox:hover {{ border: 1px solid {ORANGE}; }}
    QComboBox QAbstractItemView {{
        background-color: #1a1a1a;
        selection-background-color: {ORANGE};
        selection-color: #000;
    }}
    QPushButton {{
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 6px;
        padding: 8px 16px;
    }}
    QPushButton:hover {{ border: 1px solid {ORANGE}; color: {ORANGE}; }}
    QPushButton:pressed {{ background-color: #262626; }}
    QPushButton#primary {{
        background-color: {ORANGE};
        color: #000;
        font-weight: bold;
        border: none;
    }}
    QPushButton#primary:hover {{ background-color: #ff8c33; }}
    QPushButton#danger {{
        background-color: #2a1010;
        color: #ff6b6b;
        border: 1px solid #5a2020;
    }}
    QLabel#value {{ color: {ORANGE}; font-weight: bold; }}
    QLabel#tip {{ color: #888; font-size: 11px; }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: #333;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {ORANGE};
        width: 14px;
        height: 14px;
        margin: -6px 0;
        border-radius: 7px;
    }}
    QSlider::sub-page:horizontal {{
        background: {ORANGE};
        border-radius: 2px;
    }}
    QCheckBox::indicator:checked {{
        background-color: {ORANGE};
        border: 1px solid {ORANGE};
    }}
    QCheckBox::indicator {{
        width: 14px; height: 14px;
        border: 1px solid #444;
        border-radius: 3px;
    }}
    QWidget#navbar {{
        background-color: #161616;
        border-bottom: 1px solid #2a2a2a;
    }}
    QLabel#apptitle {{
        color: {ORANGE};
        font-size: 16px;
        font-weight: bold;
    }}
    QPushButton#navbtn {{
        background-color: transparent;
        border: none;
        border-radius: 0;
        padding: 6px 16px;
        color: #aaa;
    }}
    QPushButton#navbtn:hover {{ color: {ORANGE}; }}
    QPushButton#navbtn:checked {{
        color: {ORANGE};
        border-bottom: 2px solid {ORANGE};
        font-weight: bold;
    }}
    QPushButton#winbtn {{
        background-color: transparent;
        border: none;
        border-radius: 0;
        color: #aaa;
        font-size: 14px;
    }}
    QPushButton#winbtn:hover {{ background-color: #2a2a2a; color: #fff; }}
    QPushButton#winclose {{
        background-color: transparent;
        border: none;
        border-radius: 0;
        color: #aaa;
        font-size: 13px;
    }}
    QPushButton#winclose:hover {{ background-color: #c0392b; color: #fff; }}
    """

    class GUIConfig:
        def __init__(self) -> None:
            self.pth_path: str = ""
            self.index_path: str = ""
            self.pitch: int = 12
            self.formant: float = 0.0
            self.sr_type: str = "sr_device"
            self.block_time: float = 0.25
            self.threhold: int = -60
            self.crossfade_time: float = 0.05
            self.extra_time: float = 2.5
            self.I_noise_reduce: bool = False
            self.O_noise_reduce: bool = False
            self.rms_mix_rate: float = 0.0
            self.index_rate: float = 0.0
            self.n_cpu: int = min(n_cpu, 4)
            self.use_pv: bool = False
            self.f0method: str = "rmvpe"
            self.sg_hostapi: str = ""
            self.sg_wasapi_exclusive: bool = False
            self.sg_input_device: str = ""
            self.sg_output_device: str = ""
            self.channels: int = 2
            self.samplerate: int = 40000

    class TitleBar(QWidget):
        """自绘标题栏:按住拖动窗口,双击最大化/还原"""
        def __init__(self, win):
            super().__init__()
            self._win = win

        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton:
                # 用 Qt 原生系统移动,拖动最稳
                try:
                    self._win.windowHandle().startSystemMove()
                except Exception:
                    pass
            super().mousePressEvent(event)

        def mouseDoubleClickEvent(self, event):
            if event.button() == Qt.LeftButton:
                self._win.toggle_max_restore()
            super().mouseDoubleClickEvent(event)

    class LoadWorker(QThread):
        """后台执行耗时的模型加载 + 开流,避免 UI 冻结"""
        done = Signal(bool, str)  # (成功, 错误信息)

        def __init__(self, fn):
            super().__init__()
            self._fn = fn

        def run(self):
            try:
                self._fn()
                self.done.emit(True, "")
            except Exception:
                self.done.emit(False, traceback.format_exc())

    class GUI(QWidget):
        # 跨线程信号:音频线程 -> 主线程刷新推理耗时
        infer_time_signal = Signal(int)

        def __init__(self):
            super().__init__()
            self.gui_config = GUIConfig()
            self.config = Config()
            self.function = "vc"
            self.stream = None
            self.rvc = None
            self.hostapis = None
            self.input_devices = None
            self.output_devices = None
            self.input_devices_indices = None
            self.output_devices_indices = None
            self._maximized = False
            self.setWindowTitle("RVC 实时变声器")
            # 加载内置阿里巴巴普惠体 Heavy(打包进产品,不依赖用户是否安装)
            self.app_font_family = self._load_app_font()
            self.setStyleSheet(DARK_QSS)
            # 无边框窗口(自绘标题栏),保留系统缩放/贴边
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.setMinimumSize(560, 560)
            self.resize(680, 760)
            self.update_devices()
            self.load_config_defaults()
            self.build_ui()
            self.infer_time_signal.connect(self.on_infer_time)

        def _load_app_font(self):
            """加载内置字体,返回家族名;失败则回退微软雅黑"""
            try:
                from PySide6.QtGui import QFontDatabase
                path = os.path.join(
                    now_dir, "assets", "fonts", "Alibaba-PuHuiTi-Heavy.ttf"
                )
                if os.path.exists(path):
                    fid = QFontDatabase.addApplicationFont(path)
                    if fid >= 0:
                        fams = QFontDatabase.applicationFontFamilies(fid)
                        if fams:
                            return fams[0]
            except Exception:
                pass
            return "Microsoft YaHei"


        # ---------- 配置默认值 ----------
        def load_config_defaults(self):
            try:
                if not os.path.exists("configs/inuse/config.json"):
                    os.makedirs("configs/inuse", exist_ok=True)
                    shutil.copy("configs/config.json", "configs/inuse/config.json")
                with open("configs/inuse/config.json", "r", encoding="utf-8") as j:
                    data = json.load(j)
            except Exception:
                data = {}
            g = self.gui_config
            g.pth_path = data.get("pth_path", "")
            g.index_path = data.get("index_path", "")
            g.pitch = int(data.get("pitch", 12))
            g.formant = float(data.get("formant", 0.0))
            g.sr_type = data.get("sr_type", "sr_device")
            g.threhold = int(data.get("threhold", -60))
            g.block_time = float(data.get("block_time", 0.25))
            g.crossfade_time = float(data.get("crossfade_length", 0.05))
            g.extra_time = float(data.get("extra_time", 2.5))
            g.rms_mix_rate = float(data.get("rms_mix_rate", 0.0))
            g.index_rate = float(data.get("index_rate", 0.0))
            g.n_cpu = int(data.get("n_cpu", min(n_cpu, 4)))
            g.f0method = data.get("f0method", "rmvpe")

        # ---------- 列举模型 ----------
        def list_models(self):
            weight_root = os.getenv("weight_root", "assets/weights")
            models = []
            if os.path.isdir(weight_root):
                for f in sorted(os.listdir(weight_root)):
                    if f.endswith(".pth"):
                        models.append(f)
            return weight_root, models

        def auto_index_for(self, weight_root, pth_name):
            """给定 .pth 文件名,自动找同名 .index"""
            base = pth_name[:-4]  # 去掉 .pth
            cand = os.path.join(weight_root, base + ".index")
            if os.path.exists(cand):
                return cand
            return ""

        # ---------- 滑块行辅助 ----------
        def add_slider(self, grid, row, label, tip, key, vmin, vmax, default,
                       scale=1, fmt="{:.0f}", on_change=None):
            """
            添加一行:标签 + 滑块 + 数值显示。
            scale: 浮点参数放大倍数(QSlider 只支持整数)。
            on_change: 值变化时的回调(接收换算后的真实值),用于运行中热更新。
            """
            name_lbl = QLabel(label)
            tip_lbl = QLabel(tip)
            tip_lbl.setObjectName("tip")
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(int(round(vmin * scale)))
            slider.setMaximum(int(round(vmax * scale)))
            slider.setValue(int(round(default * scale)))
            val_lbl = QLabel(fmt.format(default))
            val_lbl.setObjectName("value")
            val_lbl.setMinimumWidth(48)

            def _changed(iv):
                real = iv / scale
                val_lbl.setText(fmt.format(real))
                if on_change is not None:
                    on_change(real)

            slider.valueChanged.connect(_changed)
            self.sliders[key] = slider
            grid.addWidget(name_lbl, row, 0)
            grid.addWidget(slider, row, 1)
            grid.addWidget(val_lbl, row, 2)
            grid.addWidget(tip_lbl, row, 3)
            return slider

        # ---------- 构建界面 ----------
        def build_ui(self):
            self.sliders = {}
            root = QVBoxLayout(self)
            root.setSpacing(0)
            root.setContentsMargins(0, 0, 0, 0)

            # ===== 顶部导航栏(自绘,无系统标题栏)=====
            nav = TitleBar(self)
            nav.setObjectName("navbar")
            nav_l = QHBoxLayout(nav)
            nav_l.setContentsMargins(14, 6, 8, 6)
            nav_l.setSpacing(6)
            title = QLabel("RVC 变声器")
            title.setObjectName("apptitle")
            # 控件级 stylesheet 优先级高于应用级全局 QSS,确保普惠体不被全局字体覆盖
            _fam = self.app_font_family or "Microsoft YaHei"
            title.setStyleSheet(
                f'color:{ORANGE}; font-family:"{_fam}"; font-size:17px; font-weight:bold;'
            )
            nav_l.addWidget(title)
            nav_l.addSpacing(18)
            self.nav_buttons = {}
            for idx, name in enumerate(["变声", "设置", "关于"]):
                b = QPushButton(name)
                b.setObjectName("navbtn")
                b.setCheckable(True)
                b.clicked.connect(lambda checked, i=idx: self.switch_page(i))
                nav_l.addWidget(b)
                self.nav_buttons[idx] = b
            nav_l.addStretch()
            # 窗口控制按钮:最小化 / 最大化-还原 / 关闭
            btn_min = QPushButton("—")
            btn_min.setObjectName("winbtn")
            btn_min.clicked.connect(self.showMinimized)
            self.btn_max = QPushButton("☐")
            self.btn_max.setObjectName("winbtn")
            self.btn_max.clicked.connect(self.toggle_max_restore)
            btn_close = QPushButton("✕")
            btn_close.setObjectName("winclose")
            btn_close.clicked.connect(self.close)
            for b in (btn_min, self.btn_max, btn_close):
                b.setFixedSize(38, 28)
                nav_l.addWidget(b)
            root.addWidget(nav)

            # ===== 分页容器 =====
            self.pages = QStackedWidget()
            self.pages.addWidget(self._build_vc_page())
            self.pages.addWidget(self._build_settings_page())
            self.pages.addWidget(self._build_about_page())
            root.addWidget(self.pages, 1)

            self.switch_page(0)
            self.sync_selection_from_config()

        def switch_page(self, index):
            self.pages.setCurrentIndex(index)
            for i, b in self.nav_buttons.items():
                b.setChecked(i == index)

        def toggle_max_restore(self):
            if self.isMaximized():
                self.showNormal()
                self.btn_max.setText("☐")
            else:
                self.showMaximized()
                self.btn_max.setText("❐")

        def nativeEvent(self, eventType, message):
            """无边框窗口的边缘拉伸(Windows WM_NCHITTEST),失败不影响运行"""
            try:
                if eventType == "windows_generic_MSG":
                    import ctypes
                    from ctypes.wintypes import MSG
                    msg = MSG.from_address(int(message))
                    if msg.message == 0x0084:  # WM_NCHITTEST
                        if self.isMaximized():
                            return False, 0
                        border = 6
                        x = (msg.lParam & 0xFFFF)
                        y = (msg.lParam >> 16) & 0xFFFF
                        # 转成 16 位有符号
                        if x >= 32768:
                            x -= 65536
                        if y >= 32768:
                            y -= 65536
                        # 用窗口本地坐标判断
                        w, h = self.width(), self.height()
                        lx = x - self.geometry().x()
                        ly = y - self.geometry().y()
                        left = lx < border
                        right = lx > w - border
                        top = ly < border
                        bottom = ly > h - border
                        if top and left:
                            return True, 13      # HTTOPLEFT
                        if top and right:
                            return True, 14      # HTTOPRIGHT
                        if bottom and left:
                            return True, 16      # HTBOTTOMLEFT
                        if bottom and right:
                            return True, 17      # HTBOTTOMRIGHT
                        if left:
                            return True, 10      # HTLEFT
                        if right:
                            return True, 11      # HTRIGHT
                        if top:
                            return True, 12      # HTTOP
                        if bottom:
                            return True, 15      # HTBOTTOM
            except Exception:
                pass
            return False, 0

        # ---------- 变声页(常用) ----------
        def _build_vc_page(self):
            page = QWidget()
            v = QVBoxLayout(page)
            v.setSpacing(12)
            v.setContentsMargins(18, 18, 18, 18)

            # 模型区
            model_box = QGroupBox("音色模型")
            mg = QGridLayout(model_box)
            self.model_combo = QComboBox()
            weight_root, models = self.list_models()
            self.model_combo.addItems(models)
            self.model_combo.currentTextChanged.connect(self.on_model_changed)
            btn_refresh = QPushButton("刷新")
            btn_refresh.clicked.connect(self.refresh_models)
            btn_browse = QPushButton("浏览…")
            btn_browse.clicked.connect(self.browse_model)
            mg.addWidget(QLabel("选择模型"), 0, 0)
            mg.addWidget(self.model_combo, 0, 1)
            mg.addWidget(btn_refresh, 0, 2)
            mg.addWidget(btn_browse, 0, 3)
            self.index_label = QLabel("索引: (未选择)")
            self.index_label.setObjectName("tip")
            mg.addWidget(self.index_label, 1, 0, 1, 4)
            v.addWidget(model_box)

            # 常用参数
            param_box = QGroupBox("常用参数(运行中可实时调整)")
            pg = QGridLayout(param_box)
            g = self.gui_config
            self.add_slider(pg, 0, "音调", "男→女 +12,女→男 -12", "pitch",
                            -16, 16, g.pitch, scale=1, fmt="{:.0f}",
                            on_change=self.hot_pitch)
            self.add_slider(pg, 1, "Index Rate", "音色相似度,推荐 0.75", "index_rate",
                            0.0, 1.0, g.index_rate, scale=100, fmt="{:.2f}",
                            on_change=self.hot_index_rate)
            v.addWidget(param_box)

            # 控制区
            ctrl_box = QGroupBox("控制")
            cg = QHBoxLayout(ctrl_box)
            self.btn_start = QPushButton("开始变声")
            self.btn_start.setObjectName("primary")
            self.btn_start.clicked.connect(self.on_start)
            self.btn_stop = QPushButton("停止")
            self.btn_stop.setObjectName("danger")
            self.btn_stop.clicked.connect(self.on_stop)
            self.btn_stop.setEnabled(False)
            cg.addWidget(self.btn_start)
            cg.addWidget(self.btn_stop)
            v.addWidget(ctrl_box)

            # 状态区
            status_box = QGroupBox("状态")
            sg_ = QHBoxLayout(status_box)
            sg_.addWidget(QLabel("推理耗时(ms):"))
            self.infer_time_label = QLabel("0")
            self.infer_time_label.setObjectName("value")
            sg_.addWidget(self.infer_time_label)
            sg_.addStretch()
            self.status_label = QLabel("就绪")
            sg_.addWidget(self.status_label)
            v.addWidget(status_box)

            v.addStretch()
            return page

        # ---------- 设置页 ----------
        def _build_settings_page(self):
            page = QWidget()
            v = QVBoxLayout(page)
            v.setSpacing(12)
            v.setContentsMargins(18, 18, 18, 18)
            g = self.gui_config

            # 设备区
            dev_box = QGroupBox("音频设备")
            dg = QGridLayout(dev_box)
            self.hostapi_combo = QComboBox()
            self.hostapi_combo.addItems(self.hostapis)
            self.hostapi_combo.currentTextChanged.connect(self.on_hostapi_changed)
            self.input_combo = QComboBox()
            self.input_combo.addItems(self.input_devices)
            self.output_combo = QComboBox()
            self.output_combo.addItems(self.output_devices)
            dg.addWidget(QLabel("驱动类型"), 0, 0)
            dg.addWidget(self.hostapi_combo, 0, 1)
            dg.addWidget(QLabel("输入设备(麦克风)"), 1, 0)
            dg.addWidget(self.input_combo, 1, 1)
            dg.addWidget(QLabel("输出设备"), 2, 0)
            dg.addWidget(self.output_combo, 2, 1)
            out_tip = QLabel("游戏语音请选 CABLE Input(已自动选择)")
            out_tip.setObjectName("tip")
            dg.addWidget(out_tip, 3, 1)
            btn_reload = QPushButton("重载设备列表")
            btn_reload.clicked.connect(self.reload_devices)
            dg.addWidget(btn_reload, 4, 1)
            v.addWidget(dev_box)

            # 监听区(方案乙:通过 Windows 系统「侦听」功能,稳定通用)
            listen_box = QGroupBox("监听(自己听到变声效果)")
            lg = QVBoxLayout(listen_box)
            listen_tip = QLabel(
                "想在耳机里听到自己变声后的声音,按以下一次性设置即可:\n"
                "1. 点下方按钮打开系统声音设置\n"
                "2. 切到「录制」选项卡,双击「CABLE Output」\n"
                "3. 在「侦听」页勾选「侦听此设备」,下方播放设备选你的耳机\n"
                "4. 确定。以后无需再设置。"
            )
            listen_tip.setObjectName("tip")
            listen_tip.setWordWrap(True)
            lg.addWidget(listen_tip)
            btn_sound = QPushButton("打开系统声音设置")
            btn_sound.clicked.connect(self.open_sound_settings)
            lg.addWidget(btn_sound)
            v.addWidget(listen_box)

            # 高级变声参数
            adv_box = QGroupBox("高级变声参数(运行中可实时调整)")
            ag = QGridLayout(adv_box)
            self.add_slider(ag, 0, "性别因子", "声线粗细,0 为不变", "formant",
                            -2.0, 2.0, g.formant, scale=100, fmt="{:.2f}",
                            on_change=self.hot_formant)
            self.add_slider(ag, 1, "响度因子", "0 保留原响度,1 用输出响度", "rms_mix_rate",
                            0.0, 1.0, g.rms_mix_rate, scale=100, fmt="{:.2f}",
                            on_change=self.hot_rms)
            self.add_slider(ag, 2, "响应阈值", "越大越能过滤环境底噪", "threhold",
                            -60, 0, g.threhold, scale=1, fmt="{:.0f}",
                            on_change=self.hot_threhold)
            ag.addWidget(QLabel("音高算法"), 3, 0)
            self.f0_combo = QComboBox()
            self.f0_combo.addItems(["rmvpe", "fcpe", "harvest", "crepe", "pm"])
            self.f0_combo.setCurrentText(g.f0method)
            self.f0_combo.currentTextChanged.connect(self.hot_f0method)
            ag.addWidget(self.f0_combo, 3, 1)
            ag.addWidget(QLabel("rmvpe 效果最好"), 3, 3)
            self.chk_i_nr = QCheckBox("输入降噪")
            self.chk_i_nr.setChecked(g.I_noise_reduce)
            self.chk_i_nr.stateChanged.connect(self.hot_i_nr)
            self.chk_o_nr = QCheckBox("输出降噪")
            self.chk_o_nr.setChecked(g.O_noise_reduce)
            self.chk_o_nr.stateChanged.connect(self.hot_o_nr)
            ag.addWidget(self.chk_i_nr, 4, 0)
            ag.addWidget(self.chk_o_nr, 4, 1)
            v.addWidget(adv_box)

            # 性能参数
            perf_box = QGroupBox("性能参数(修改后需重新开始变声)")
            fg = QGridLayout(perf_box)
            self.add_slider(fg, 0, "采样长度", "越小延迟越低,但越吃性能", "block_time",
                            0.05, 1.0, g.block_time, scale=100, fmt="{:.2f}s")
            self.add_slider(fg, 1, "淡入淡出", "过渡时长,默认 0.05", "crossfade_time",
                            0.01, 0.5, g.crossfade_time, scale=100, fmt="{:.2f}s")
            self.add_slider(fg, 2, "额外推理时长", "越大越稳但越吃显存", "extra_time",
                            0.5, 5.0, g.extra_time, scale=100, fmt="{:.2f}s")
            v.addWidget(perf_box)

            v.addStretch()
            return page

        # ---------- 关于页 ----------
        def _build_about_page(self):
            page = QWidget()
            v = QVBoxLayout(page)
            v.setSpacing(14)
            v.setContentsMargins(24, 24, 24, 24)
            title = QLabel("RVC 实时变声器")
            title.setObjectName("apptitle")
            v.addWidget(title)
            v.addWidget(QLabel("版本 1.0"))
            info = QLabel(
                "实时 AI 变声器,支持男↔女音色转换。\n\n"
                "游戏语音使用方法:\n"
                "1. 输出设备选 CABLE Input(默认已选)\n"
                "2. 游戏内麦克风选 CABLE Output\n"
                "3. 想自己听到变声,在「设置」页按引导开启系统侦听\n\n"
                "推荐参数:男→女 音调 +12,F0 算法 rmvpe,Index 0.75"
            )
            info.setObjectName("tip")
            info.setWordWrap(True)
            v.addWidget(info)
            v.addStretch()
            disclaimer = QLabel("基于开源项目 RVC-Project 构建")
            disclaimer.setObjectName("tip")
            v.addWidget(disclaimer)
            return page

        def sync_selection_from_config(self):
            """根据配置里的 pth_path 预选下拉框,并默认选中 CABLE Input 输出"""
            weight_root, models = self.list_models()
            cur = os.path.basename(self.gui_config.pth_path) if self.gui_config.pth_path else ""
            if cur and cur in models:
                self.model_combo.setCurrentText(cur)
                self.on_model_changed(cur)
            elif models:
                self.on_model_changed(self.model_combo.currentText())
            # 输出设备默认选 VB-Cable(前缀匹配,MME 会截断设备名)
            self.select_default_output()

        def select_default_output(self):
            """输出下拉默认选 CABLE Input(前缀匹配);监听下拉默认选非 CABLE 的真实设备"""
            cable_idx = -1
            for i, name in enumerate(self.output_devices):
                if name.startswith("CABLE Input"):
                    cable_idx = i
                    break
            if cable_idx >= 0:
                self.output_combo.setCurrentIndex(cable_idx)
            else:
                # 未检测到 VB-Cable,提示
                if hasattr(self, "status_label"):
                    self.status_label.setText("未检测到 VB-Cable,游戏语音需先安装")

        # ---------- 事件 ----------
        def on_model_changed(self, pth_name):
            if not pth_name:
                return
            weight_root, _ = self.list_models()
            pth_path = os.path.join(weight_root, pth_name)
            index_path = self.auto_index_for(weight_root, pth_name)
            self.gui_config.pth_path = pth_path
            self.gui_config.index_path = index_path
            if index_path:
                self.index_label.setText(f"索引: {os.path.basename(index_path)} (自动配对)")
            else:
                self.index_label.setText("索引: (未找到同名 .index)")

        def refresh_models(self):
            cur = self.model_combo.currentText()
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            _, models = self.list_models()
            self.model_combo.addItems(models)
            self.model_combo.blockSignals(False)
            if cur in models:
                self.model_combo.setCurrentText(cur)
            elif models:
                self.on_model_changed(self.model_combo.currentText())

        def browse_model(self):
            weight_root, _ = self.list_models()
            path, _ = QFileDialog.getOpenFileName(
                self, "选择 .pth 模型文件", weight_root, "模型文件 (*.pth)"
            )
            if path:
                self.gui_config.pth_path = path
                # 自动找同名 index
                base = path[:-4]
                idx = base + ".index"
                self.gui_config.index_path = idx if os.path.exists(idx) else ""
                self.index_label.setText(
                    f"索引: {os.path.basename(self.gui_config.index_path)}"
                    if self.gui_config.index_path
                    else "索引: (未找到同名 .index)"
                )
                self.status_label.setText(f"已选: {os.path.basename(path)}")

        def on_hostapi_changed(self, name):
            self.update_devices(hostapi_name=name)
            self.input_combo.blockSignals(True)
            self.output_combo.blockSignals(True)
            self.input_combo.clear()
            self.input_combo.addItems(self.input_devices)
            self.output_combo.clear()
            self.output_combo.addItems(self.output_devices)
            self.input_combo.blockSignals(False)
            self.output_combo.blockSignals(False)

        def reload_devices(self):
            cur_host = self.hostapi_combo.currentText()
            self.update_devices(hostapi_name=cur_host)
            self.hostapi_combo.blockSignals(True)
            self.hostapi_combo.clear()
            self.hostapi_combo.addItems(self.hostapis)
            self.hostapi_combo.setCurrentText(cur_host)
            self.hostapi_combo.blockSignals(False)
            self.on_hostapi_changed(cur_host)

        def on_infer_time(self, ms):
            self.infer_time_label.setText(str(ms))

        def open_sound_settings(self):
            """打开 Windows 声音设置(录制页),供用户配置侦听/默认设备"""
            try:
                import subprocess
                # 录制选项卡(侦听功能在这里);参数 ,,1 = 录制页
                subprocess.Popen(["control", "mmsys.cpl,,1"], shell=True)
            except Exception:
                printt("打开声音设置失败:\n%s", traceback.format_exc())

        # ---------- 参数热更新 ----------
        def hot_pitch(self, val):
            self.gui_config.pitch = int(val)
            if self.rvc is not None:
                self.rvc.change_key(int(val))

        def hot_formant(self, val):
            self.gui_config.formant = float(val)
            if self.rvc is not None:
                self.rvc.change_formant(float(val))

        def hot_index_rate(self, val):
            self.gui_config.index_rate = float(val)
            if self.rvc is not None:
                self.rvc.change_index_rate(float(val))

        def hot_rms(self, val):
            self.gui_config.rms_mix_rate = float(val)

        def hot_threhold(self, val):
            self.gui_config.threhold = int(val)

        def hot_f0method(self, text):
            self.gui_config.f0method = text

        def hot_i_nr(self, state):
            self.gui_config.I_noise_reduce = self.chk_i_nr.isChecked()

        def hot_o_nr(self, state):
            self.gui_config.O_noise_reduce = self.chk_o_nr.isChecked()

        def on_start(self):
            if not self.gui_config.pth_path or not os.path.exists(self.gui_config.pth_path):
                QMessageBox.warning(self, "提示", "请先选择一个有效的音色模型(.pth)")
                return
            if not self.input_combo.currentText() or not self.output_combo.currentText():
                QMessageBox.warning(self, "提示", "请选择输入和输出设备")
                return
            # 记录设备/参数
            self.gui_config.sg_hostapi = self.hostapi_combo.currentText()
            self.gui_config.sg_input_device = self.input_combo.currentText()
            self.gui_config.sg_output_device = self.output_combo.currentText()
            # 同步性能参数(启动时读取,滑块值 -> gui_config)
            self.gui_config.block_time = self.sliders["block_time"].value() / 100
            self.gui_config.crossfade_time = self.sliders["crossfade_time"].value() / 100
            self.gui_config.extra_time = self.sliders["extra_time"].value() / 100
            try:
                self.set_devices(
                    self.gui_config.sg_input_device, self.gui_config.sg_output_device
                )
            except Exception:
                traceback.print_exc()
                QMessageBox.critical(self, "启动失败", "设备设置失败,请检查音频设备")
                return
            # 模型加载 + 开流放后台线程,避免 UI 冻结(约 10 秒)
            self.btn_start.setEnabled(False)
            self.btn_start.setText("加载中…")
            self.status_label.setText("正在加载模型,请稍候(约 10 秒)…")
            self._load_worker = LoadWorker(self.start_vc)
            self._load_worker.done.connect(self.on_load_done)
            self._load_worker.start()

        def on_load_done(self, ok, err):
            self.btn_start.setText("开始变声")
            if ok:
                # 模型已在后台加载完;音频流必须在主线程创建(COM 环境稳定)
                try:
                    self.start_stream()
                    self.btn_stop.setEnabled(True)
                    self.status_label.setText("变声运行中")
                except Exception:
                    import traceback as _tb
                    self.btn_start.setEnabled(True)
                    msg = _tb.format_exc()
                    printt("开音频流失败:\n%s", msg)
                    QMessageBox.critical(self, "启动失败", msg[-800:])
                    self.status_label.setText("启动失败")
            else:
                self.btn_start.setEnabled(True)
                printt("启动失败:\n%s", err)
                QMessageBox.critical(self, "启动失败", (err or "")[-800:])
                self.status_label.setText("启动失败")

        def on_stop(self):
            self.stop_stream()
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_label.setText("已停止")

        def closeEvent(self, event):
            # 停止音频流,释放麦克风/输出设备
            try:
                self.stop_stream()
            except Exception:
                pass
            # 终止 Harvest 子进程,防止残留占用设备(异常退出的保险)
            try:
                for p in harvest_procs:
                    if p.is_alive():
                        p.terminate()
            except Exception:
                pass
            event.accept()

        # ================= 以下音频引擎逻辑搬运自 gui_v1.py =================
        def start_vc(self):
            torch.cuda.empty_cache()
            self.rvc = rvc_for_realtime.RVC(
                self.gui_config.pitch,
                self.gui_config.formant,
                self.gui_config.pth_path,
                self.gui_config.index_path,
                self.gui_config.index_rate,
                self.gui_config.n_cpu,
                inp_q,
                opt_q,
                self.config,
                self.rvc if self.rvc is not None else None,
            )
            self.gui_config.samplerate = (
                self.rvc.tgt_sr
                if self.gui_config.sr_type == "sr_model"
                else self.get_device_samplerate()
            )
            self.gui_config.channels = self.get_device_channels()
            self.zc = self.gui_config.samplerate // 100
            self.block_frame = (
                int(
                    np.round(
                        self.gui_config.block_time
                        * self.gui_config.samplerate
                        / self.zc
                    )
                )
                * self.zc
            )
            self.block_frame_16k = 160 * self.block_frame // self.zc
            self.crossfade_frame = (
                int(
                    np.round(
                        self.gui_config.crossfade_time
                        * self.gui_config.samplerate
                        / self.zc
                    )
                )
                * self.zc
            )
            self.sola_buffer_frame = min(self.crossfade_frame, 4 * self.zc)
            self.sola_search_frame = self.zc
            self.extra_frame = (
                int(
                    np.round(
                        self.gui_config.extra_time
                        * self.gui_config.samplerate
                        / self.zc
                    )
                )
                * self.zc
            )
            self.input_wav: torch.Tensor = torch.zeros(
                self.extra_frame
                + self.crossfade_frame
                + self.sola_search_frame
                + self.block_frame,
                device=self.config.device,
                dtype=torch.float32,
            )
            self.input_wav_denoise: torch.Tensor = self.input_wav.clone()
            self.input_wav_res: torch.Tensor = torch.zeros(
                160 * self.input_wav.shape[0] // self.zc,
                device=self.config.device,
                dtype=torch.float32,
            )
            self.rms_buffer: np.ndarray = np.zeros(4 * self.zc, dtype="float32")
            self.sola_buffer: torch.Tensor = torch.zeros(
                self.sola_buffer_frame, device=self.config.device, dtype=torch.float32
            )
            self.nr_buffer: torch.Tensor = self.sola_buffer.clone()
            self.output_buffer: torch.Tensor = self.input_wav.clone()
            self.skip_head = self.extra_frame // self.zc
            self.return_length = (
                self.block_frame + self.sola_buffer_frame + self.sola_search_frame
            ) // self.zc
            self.fade_in_window: torch.Tensor = (
                torch.sin(
                    0.5
                    * np.pi
                    * torch.linspace(
                        0.0,
                        1.0,
                        steps=self.sola_buffer_frame,
                        device=self.config.device,
                        dtype=torch.float32,
                    )
                )
                ** 2
            )
            self.fade_out_window: torch.Tensor = 1 - self.fade_in_window
            self.resampler = tat.Resample(
                orig_freq=self.gui_config.samplerate,
                new_freq=16000,
                dtype=torch.float32,
            ).to(self.config.device)
            if self.rvc.tgt_sr != self.gui_config.samplerate:
                self.resampler2 = tat.Resample(
                    orig_freq=self.rvc.tgt_sr,
                    new_freq=self.gui_config.samplerate,
                    dtype=torch.float32,
                ).to(self.config.device)
            else:
                self.resampler2 = None
            self.tg = TorchGate(
                sr=self.gui_config.samplerate, n_fft=4 * self.zc, prop_decrease=0.9
            ).to(self.config.device)
            # 注意:不在此处开音频流。start_vc 跑在后台线程,若在此建 sd.Stream,
            # 线程结束后其 COM 环境被销毁,流会名存实亡(能启动但无声、读不到麦克风)。
            # 音频流改由主线程的 on_load_done 调用 start_stream() 创建。

        def start_stream(self):
            global flag_vc
            if not flag_vc:
                flag_vc = True
                if (
                    "WASAPI" in self.gui_config.sg_hostapi
                    and self.gui_config.sg_wasapi_exclusive
                ):
                    extra_settings = sd.WasapiSettings(exclusive=True)
                else:
                    extra_settings = None
                self.stream = sd.Stream(
                    callback=self.audio_callback,
                    blocksize=self.block_frame,
                    samplerate=self.gui_config.samplerate,
                    channels=self.gui_config.channels,
                    dtype="float32",
                    extra_settings=extra_settings,
                )
                self.stream.start()

        def stop_stream(self):
            global flag_vc
            if flag_vc:
                flag_vc = False
                if self.stream is not None:
                    self.stream.abort()
                    self.stream.close()
                    self.stream = None

        def audio_callback(
            self, indata: np.ndarray, outdata: np.ndarray, frames, times, status
        ):
            """音频处理(运行在 sounddevice 线程)"""
            global flag_vc
            start_time = time.perf_counter()
            indata = librosa.to_mono(indata.T)
            if self.gui_config.threhold > -60:
                indata = np.append(self.rms_buffer, indata)
                rms = librosa.feature.rms(
                    y=indata, frame_length=4 * self.zc, hop_length=self.zc
                )[:, 2:]
                self.rms_buffer[:] = indata[-4 * self.zc :]
                indata = indata[2 * self.zc - self.zc // 2 :]
                db_threhold = (
                    librosa.amplitude_to_db(rms, ref=1.0)[0] < self.gui_config.threhold
                )
                for i in range(db_threhold.shape[0]):
                    if db_threhold[i]:
                        indata[i * self.zc : (i + 1) * self.zc] = 0
                indata = indata[self.zc // 2 :]
            self.input_wav[: -self.block_frame] = self.input_wav[
                self.block_frame :
            ].clone()
            self.input_wav[-indata.shape[0] :] = torch.from_numpy(indata).to(
                self.config.device
            )
            self.input_wav_res[: -self.block_frame_16k] = self.input_wav_res[
                self.block_frame_16k :
            ].clone()
            if self.gui_config.I_noise_reduce:
                self.input_wav_denoise[: -self.block_frame] = self.input_wav_denoise[
                    self.block_frame :
                ].clone()
                input_wav = self.input_wav[-self.sola_buffer_frame - self.block_frame :]
                input_wav = self.tg(
                    input_wav.unsqueeze(0), self.input_wav.unsqueeze(0)
                ).squeeze(0)
                input_wav[: self.sola_buffer_frame] *= self.fade_in_window
                input_wav[: self.sola_buffer_frame] += (
                    self.nr_buffer * self.fade_out_window
                )
                self.input_wav_denoise[-self.block_frame :] = input_wav[
                    : self.block_frame
                ]
                self.nr_buffer[:] = input_wav[self.block_frame :]
                self.input_wav_res[-self.block_frame_16k - 160 :] = self.resampler(
                    self.input_wav_denoise[-self.block_frame - 2 * self.zc :]
                )[160:]
            else:
                self.input_wav_res[-160 * (indata.shape[0] // self.zc + 1) :] = (
                    self.resampler(self.input_wav[-indata.shape[0] - 2 * self.zc :])[
                        160:
                    ]
                )
            if self.function == "vc":
                infer_wav = self.rvc.infer(
                    self.input_wav_res,
                    self.block_frame_16k,
                    self.skip_head,
                    self.return_length,
                    self.gui_config.f0method,
                )
                if self.resampler2 is not None:
                    infer_wav = self.resampler2(infer_wav)
            elif self.gui_config.I_noise_reduce:
                infer_wav = self.input_wav_denoise[self.extra_frame :].clone()
            else:
                infer_wav = self.input_wav[self.extra_frame :].clone()
            if self.gui_config.O_noise_reduce and self.function == "vc":
                self.output_buffer[: -self.block_frame] = self.output_buffer[
                    self.block_frame :
                ].clone()
                self.output_buffer[-self.block_frame :] = infer_wav[-self.block_frame :]
                infer_wav = self.tg(
                    infer_wav.unsqueeze(0), self.output_buffer.unsqueeze(0)
                ).squeeze(0)
            if self.gui_config.rms_mix_rate < 1 and self.function == "vc":
                if self.gui_config.I_noise_reduce:
                    input_wav = self.input_wav_denoise[self.extra_frame :]
                else:
                    input_wav = self.input_wav[self.extra_frame :]
                rms1 = librosa.feature.rms(
                    y=input_wav[: infer_wav.shape[0]].cpu().numpy(),
                    frame_length=4 * self.zc,
                    hop_length=self.zc,
                )
                rms1 = torch.from_numpy(rms1).to(self.config.device)
                rms1 = F.interpolate(
                    rms1.unsqueeze(0),
                    size=infer_wav.shape[0] + 1,
                    mode="linear",
                    align_corners=True,
                )[0, 0, :-1]
                rms2 = librosa.feature.rms(
                    y=infer_wav[:].cpu().numpy(),
                    frame_length=4 * self.zc,
                    hop_length=self.zc,
                )
                rms2 = torch.from_numpy(rms2).to(self.config.device)
                rms2 = F.interpolate(
                    rms2.unsqueeze(0),
                    size=infer_wav.shape[0] + 1,
                    mode="linear",
                    align_corners=True,
                )[0, 0, :-1]
                rms2 = torch.max(rms2, torch.zeros_like(rms2) + 1e-3)
                infer_wav *= torch.pow(
                    rms1 / rms2, torch.tensor(1 - self.gui_config.rms_mix_rate)
                )
            # SOLA
            conv_input = infer_wav[
                None, None, : self.sola_buffer_frame + self.sola_search_frame
            ]
            cor_nom = F.conv1d(conv_input, self.sola_buffer[None, None, :])
            cor_den = torch.sqrt(
                F.conv1d(
                    conv_input**2,
                    torch.ones(1, 1, self.sola_buffer_frame, device=self.config.device),
                )
                + 1e-8
            )
            if sys.platform == "darwin":
                _, sola_offset = torch.max(cor_nom[0, 0] / cor_den[0, 0])
                sola_offset = sola_offset.item()
            else:
                sola_offset = torch.argmax(cor_nom[0, 0] / cor_den[0, 0])
            infer_wav = infer_wav[sola_offset:]
            if "privateuseone" in str(self.config.device) or not self.gui_config.use_pv:
                infer_wav[: self.sola_buffer_frame] *= self.fade_in_window
                infer_wav[: self.sola_buffer_frame] += (
                    self.sola_buffer * self.fade_out_window
                )
            else:
                infer_wav[: self.sola_buffer_frame] = phase_vocoder(
                    self.sola_buffer,
                    infer_wav[: self.sola_buffer_frame],
                    self.fade_out_window,
                    self.fade_in_window,
                )
            self.sola_buffer[:] = infer_wav[
                self.block_frame : self.block_frame + self.sola_buffer_frame
            ]
            outdata[:] = (
                infer_wav[: self.block_frame]
                .repeat(self.gui_config.channels, 1)
                .t()
                .cpu()
                .numpy()
            )
            total_time = time.perf_counter() - start_time
            if flag_vc:
                self.infer_time_signal.emit(int(total_time * 1000))

        def update_devices(self, hostapi_name=None):
            """获取设备列表"""
            global flag_vc
            flag_vc = False
            sd._terminate()
            sd._initialize()
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            for hostapi in hostapis:
                for device_idx in hostapi["devices"]:
                    devices[device_idx]["hostapi_name"] = hostapi["name"]
            self.hostapis = [hostapi["name"] for hostapi in hostapis]
            if hostapi_name not in self.hostapis:
                hostapi_name = self.hostapis[0]
            self.input_devices = [
                d["name"]
                for d in devices
                if d["max_input_channels"] > 0 and d["hostapi_name"] == hostapi_name
            ]
            self.output_devices = [
                d["name"]
                for d in devices
                if d["max_output_channels"] > 0 and d["hostapi_name"] == hostapi_name
            ]
            self.input_devices_indices = [
                d["index"] if "index" in d else d["name"]
                for d in devices
                if d["max_input_channels"] > 0 and d["hostapi_name"] == hostapi_name
            ]
            self.output_devices_indices = [
                d["index"] if "index" in d else d["name"]
                for d in devices
                if d["max_output_channels"] > 0 and d["hostapi_name"] == hostapi_name
            ]

        def set_devices(self, input_device, output_device):
            """设置输入输出设备"""
            sd.default.device[0] = self.input_devices_indices[
                self.input_devices.index(input_device)
            ]
            sd.default.device[1] = self.output_devices_indices[
                self.output_devices.index(output_device)
            ]
            printt("Input device: %s:%s", str(sd.default.device[0]), input_device)
            printt("Output device: %s:%s", str(sd.default.device[1]), output_device)

        def get_device_samplerate(self):
            return int(
                sd.query_devices(device=sd.default.device[0])["default_samplerate"]
            )

        def get_device_channels(self):
            max_input_channels = sd.query_devices(device=sd.default.device[0])[
                "max_input_channels"
            ]
            max_output_channels = sd.query_devices(device=sd.default.device[1])[
                "max_output_channels"
            ]
            return min(max_input_channels, max_output_channels, 2)

    # app 与闪屏已在文件顶部创建;此处构建主窗口并关闭闪屏
    gui = GUI()
    gui.show()
    splash.finish(gui)
    sys.exit(app.exec())
