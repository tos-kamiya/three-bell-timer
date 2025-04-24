import argparse
import colorsys
import os
import platform
import shutil
import sys
import time
from typing import List, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPen

try:
    from .__about__ import __version__
except ImportError as e:
    __version__ = "(unknown)"


def clip01(v: float) -> float:
    return max(0.0, min(1.0, v))


def clip255(v: float) -> int:
    return max(0, min(255, int(v)))


def modify_hsv(rgb: Tuple[int, int, int], h: float = 0.0, s: float = 0.0, v: float = 0.0) -> Tuple[int, int, int]:
    r, g, b = rgb
    rgb01 = (r / 255, g / 255, b / 255)
    h0, s0, v0 = colorsys.rgb_to_hsv(*rgb01)
    new_h = (h0 + h) % 1.0
    new_s = clip01(s0 + s)
    new_v = clip01(v0 + v)
    r2, g2, b2 = colorsys.hsv_to_rgb(new_h, new_s, new_v)
    return clip255(r2 * 255), clip255(g2 * 255), clip255(b2 * 255)


def interpolate_rgb(
    color1: Tuple[int, int, int], color2: Optional[Tuple[int, int, int]] = None, ratio: float = 1.0
) -> Tuple[int, int, int]:
    if color2 is None:
        color2 = (0, 0, 0)
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    r = clip255((1.0 - ratio) * r2 + ratio * r1)
    g = clip255((1.0 - ratio) * g2 + ratio * g1)
    b = clip255((1.0 - ratio) * b2 + ratio * b1)
    return (r, g, b)


def generate_desktop_file():
    if platform.system() != "Linux":
        sys.exit("Error: .desktop file is valid only on Linux system.")

    exec_path = shutil.which("3bt") or os.path.abspath(sys.argv[0])

    icon_path = find_icon_file("icon256.png") or ""

    desktop_file_content = f"""[Desktop Entry]
Name=Three-bell timer
Comment=A lightweight timer designed for presentations.
Exec={exec_path}
Icon={icon_path}
Terminal=false
Type=Application
Categories=Utility;
"""
    dest_file = os.path.join(os.getcwd(), "3bt.desktop")

    try:
        with open(dest_file, "w") as f:
            f.write(desktop_file_content)
        print(f".desktop file generated at {dest_file}", file=sys.stderr)
        print("To integrate with your system, copy this file to ~/.local/share/applications/", file=sys.stderr)
        print("For example:", file=sys.stderr)
        print("  cp 3bt.desktop ~/.local/share/applications/", file=sys.stderr)
    except Exception as e:
        sys.exit(f"Error: Failed to generate .desktop file: {e}")


def find_icon_file(filename):
    base_dirs = []
    pkg_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))
    base_dirs.append(pkg_data_dir)
    try:
        pyinstaller_data_dir = sys._MEIPASS
        base_dirs.append(pyinstaller_data_dir)
    except Exception:
        pass
    base_dirs.append(os.path.abspath("."))

    for b in base_dirs:
        icon_path = os.path.join(b, filename)
        if os.path.exists(icon_path):
            return icon_path
    return None


# ---- Time Settings Dialog ----
class TimeSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget = None, time1: int = 10, time2: int = 15, time3: int = 20):
        super().__init__(parent)
        self.setWindowTitle("Change Bell Times")
        layout: QtWidgets.QFormLayout = QtWidgets.QFormLayout(self)

        self.spin1: QtWidgets.QSpinBox = QtWidgets.QSpinBox(self)
        self.spin1.setMinimum(1)
        self.spin1.setMaximum(999)
        self.spin1.setValue(time1)

        self.spin2: QtWidgets.QSpinBox = QtWidgets.QSpinBox(self)
        self.spin2.setMinimum(1)
        self.spin2.setMaximum(999)
        self.spin2.setValue(time2)

        self.spin3: QtWidgets.QSpinBox = QtWidgets.QSpinBox(self)
        self.spin3.setMinimum(1)
        self.spin3.setMaximum(999)
        self.spin3.setValue(time3)

        layout.addRow("Bell 1 (minutes):", self.spin1)
        layout.addRow("Bell 2 (minutes):", self.spin2)
        layout.addRow("Bell 3 (minutes):", self.spin3)

        button_box: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(self)
        button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        # Change the Ok button text to "Initialize"
        button_box.button(QtWidgets.QDialogButtonBox.Ok).setText("Initialize")
        layout.addWidget(button_box)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)


# ---- Timer Model ----
class TimerModel(QtCore.QObject):
    timeUpdated = QtCore.pyqtSignal()
    stateChanged = QtCore.pyqtSignal()

    def __init__(self, t1: int, t2: int, t3: int):
        super().__init__()
        self.hint_time = t1
        self.presentation_end = max(t1, t2)
        self.total_minutes = max(self.presentation_end, t3)
        self._accum = 0.0
        self._start = time.time()
        self._paused = True

    def tick(self):
        self.timeUpdated.emit()

    def toggle_pause(self):
        if self._paused:
            self._start = time.time()
        else:
            self._accum += time.time() - self._start
        self._paused = not self._paused
        self.stateChanged.emit()

    def reset(self):
        self._accum = 0.0
        self._start = time.time()
        self._paused = True
        self.stateChanged.emit()

    def elapsed(self) -> float:
        return self._accum if self._paused else self._accum + (time.time() - self._start)

    @property
    def is_paused(self) -> bool:
        return self._paused


# ---- TimerBar (View) ----
class TimerBar(QtWidgets.QWidget):
    def __init__(self, model: TimerModel, running_height: int = 10):
        super().__init__()
        self.model = model
        self.running_height = running_height
        model.timeUpdated.connect(self.update)
        model.stateChanged.connect(self.update)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), (self.height() if self.model.is_paused else self.running_height)
        gap, border = 2, 0.5
        mw = w / self.model.total_minutes
        r = max(0.0, (h - 2 * gap) / 4)
        mc = QColor(255, 255, 255)
        mc.setAlpha(240)
        el = self.model.elapsed()
        for i in range(self.model.total_minutes):
            x = i * mw
            rect = QRectF(x + gap, gap, mw - 2 * gap, h - 2 * gap)
            if i < self.model.hint_time:
                base = (0, 48, 146)
            elif i < self.model.presentation_end:
                base = (0, 135, 158)
            else:
                base = (255, 171, 91)
            lc = QColor(*interpolate_rgb(base, (255, 255, 255), 0.7))
            lc.setAlpha(130)
            dc = QColor(*base)
            dc.setAlpha(250)
            painter.setPen(Qt.NoPen)
            s_sec, e_sec = i * 60, (i + 1) * 60
            if el >= e_sec:
                painter.setBrush(dc)
                painter.drawRoundedRect(rect, r, r)
            elif el <= s_sec:
                painter.setBrush(lc)
                painter.drawRoundedRect(rect, r, r)
            else:
                frac = (el - s_sec) / 60.0
                painter.setBrush(lc)
                painter.drawRoundedRect(rect, r, r)
                dw = rect.width() * frac
                clip = QRectF(rect.left(), rect.top(), dw, rect.height())
                painter.save()
                painter.setClipRect(clip)
                painter.setBrush(dc)
                painter.drawRoundedRect(rect, r, r)
                painter.restore()
                n = (int(time.time()) % 3) + 1 if not self.model.is_paused else 1
                ms, sp = (h - 2 * gap) * 0.72, 1
                hx = rect.left() + dw - ms / 2
                painter.setBrush(mc)
                painter.setPen(Qt.NoPen)
                for j in range(n):
                    painter.drawEllipse(QRectF(hx + j * (ms + sp), (h - ms) / 2, ms, ms))
            if self.model.is_paused:
                bc = QColor(*modify_hsv(base, v=0.2, s=0.1))
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(bc, border))
                painter.drawRoundedRect(rect, r, r)
        if self.model.is_paused:
            area = h
            tri = QtGui.QPolygonF(
                [QPointF(area * 0.3, area * 0.2), QPointF(area * 0.3, area * 0.8), QPointF(area * 0.8, area * 0.5)]
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(mc)
            painter.drawPolygon(tri)
            font = painter.font()
            font.setPointSizeF(h * 0.5)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(mc)
            for mark in (self.model.hint_time, self.model.presentation_end, self.model.total_minutes):
                box = QRectF(mark * mw - (mw * 3 + gap + border), 0, mw * 3, h)
                painter.drawText(box, Qt.AlignRight | Qt.AlignVCenter, str(mark))


# ---- Presentation Window ----
class PresentationTimerWindow(QtWidgets.QMainWindow):
    def __init__(self, manager, model: TimerModel, display_index: int, pos: str, height: int):
        super().__init__()
        self.manager = manager
        self.model = model
        self.display_index = display_index
        self.position = pos
        self.margin, self.paused_h = 2, 40
        self.running_h = min(self.paused_h, max(height, 10))
        self.timerBar = TimerBar(model, height)
        self.setCentralWidget(self.timerBar)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        model.stateChanged.connect(self.adjustPosition)
        self.adjustPosition()

    def adjustPosition(self):
        screens = QtWidgets.QApplication.screens()
        scr = screens[self.display_index] if self.display_index < len(screens) else screens[0]
        avail = scr.availableGeometry()
        h = self.paused_h if self.model.is_paused else self.running_h
        x = avail.left() + self.margin
        w = avail.width() - 2 * self.margin
        y = avail.top() + self.margin if self.position == "top" else avail.bottom() - h - self.margin
        self.setGeometry(x, y, w, h)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.model.is_paused and e.pos().x() < self.paused_h:
            self.model.toggle_pause()
            return
        if e.button() in (Qt.LeftButton, Qt.RightButton):
            menu = QtWidgets.QMenu(self)
            cyc = menu.addAction("Cycle Display Target")
            cyc.triggered.connect(self.manager.cycle_display_target)
            menu.addSeparator()
            resume = menu.addAction("Resume / Pause")
            change = menu.addAction("Change Bell Times")
            menu.addSeparator()
            move_top = menu.addAction("Move to Top")
            move_bottom = menu.addAction("Move to Bottom")
            menu.addSeparator()
            exit_a = menu.addAction("Exit")
            action = menu.exec_(e.globalPos())
            if action == resume:
                self.model.toggle_pause()
            elif action == move_top:
                self.position = "top"
                self.adjustPosition()
            elif action == move_bottom:
                self.position = "bottom"
                self.adjustPosition()
            elif action == change:
                self.manager.update_time_settings()
            elif action == exit_a:
                QtWidgets.QApplication.quit()


# ---- Manager / Application ----
class PresentationTimerApp:
    def __init__(self, args):
        # Initialize QApplication
        self.app = QtWidgets.QApplication(sys.argv)
        icon_path = find_icon_file("icon.ico")
        if icon_path:
            self.app.setWindowIcon(QIcon(icon_path))

        # TimerModel remains the same
        self.model = TimerModel(args.time1, args.time2, args.time3)

        # Gather all screens
        screens = self.app.screens()

        # Parse --display: either 'all' or comma-separated indices
        disp_arg = args.display.lower()
        if disp_arg == "all":
            disp_indices = list(range(len(screens)))
        else:
            disp_indices = [int(i) for i in disp_arg.split(",")]

        # Build the cycle modes: None means “all selected”, then each index
        self.display_modes: List[Optional[int]] = [None] + disp_indices
        self.current_display_mode: int = 0

        # Create one window per selected display index
        self.windows: List[PresentationTimerWindow] = []
        for idx in disp_indices:
            w = PresentationTimerWindow(self, self.model, idx, args.pos, args.pixel_height)
            self.windows.append(w)

        # Show initial set of windows
        self.update_window_visibility()

        # Set up system tray, tick timer, etc. (unchanged)
        self._setup_tray()
        self.tick_timer = QtCore.QTimer()
        self.tick_timer.timeout.connect(self.model.tick)
        self.tick_timer.start(100)

    def cycle_display_target(self):
        self.current_display_mode = (self.current_display_mode + 1) % len(self.display_modes)
        self.update_window_visibility()

    def update_window_visibility(self):
        mode = self.display_modes[self.current_display_mode]
        for win in self.windows:
            if mode is None or win.display_index == mode:
                win.show()
            else:
                win.hide()

    def _setup_tray(self):
        self.tray = QtWidgets.QSystemTrayIcon(self.app)
        app_icon = find_icon_file('icon.ico')
        if app_icon:
            qicon = QtGui.QIcon(app_icon)
            self.app.setWindowIcon(qicon)
        else:
            qicon = self.app.windowIcon()
        self.tray.setIcon(qicon)

        menu = QtWidgets.QMenu()
        cyc = menu.addAction('Cycle Display Target')
        cyc.triggered.connect(self.cycle_display_target)
        menu.addSeparator()
        resume = menu.addAction('Resume / Pause')
        resume.triggered.connect(self.model.toggle_pause)
        change = menu.addAction('Change Bell Times')
        change.triggered.connect(self.update_time_settings)
        menu.addSeparator()
        exit_a = menu.addAction('Exit')
        exit_a.triggered.connect(QtWidgets.QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def update_time_settings(self):
        # open dialog on first window
        dialog = TimeSettingsDialog(self.windows[0], self.model.hint_time, self.model.presentation_end, self.model.total_minutes)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        t1 = dialog.spin1.value(); t2 = dialog.spin2.value(); t3 = dialog.spin3.value()
        self.model.hint_time = t1
        self.model.presentation_end = max(t1, t2)
        self.model.total_minutes = max(self.model.presentation_end, t3)
        self.model.reset()
        for win in self.windows:
            win.adjustPosition()

    def run(self):
        sys.exit(self.app.exec_())


def main():
    parser = argparse.ArgumentParser(description="Three-bell Timer")
    parser.add_argument("times", type=int, nargs="*", help="bell times: 1 ⇒ all three; 2 ⇒ first/last two; 3 ⇒ each")
    parser.add_argument(
        "--display",
        "-d",
        type=str,
        default="all",
        help="which displays to use: 'all', or comma-separated indices (e.g. '0,1')",
    )
    parser.add_argument("--pos", "-p", choices=["top", "bottom"], default="top", help="window position on screen")
    parser.add_argument("--pixel-height", "-s", type=int, default=10, help="height of the running timer bar")
    parser.add_argument("--generate-desktop", action="store_true", help="output a .desktop file and exit")
    args = parser.parse_args()

    if args.generate_desktop:
        generate_desktop_file()
        sys.exit(0)

    # normalize time arguments
    if len(args.times) == 1:
        args.time1 = args.time2 = args.time3 = args.times[0]
    elif len(args.times) == 2:
        args.time1, args.time2 = args.times
        args.time3 = args.time2
    elif len(args.times) >= 3:
        args.time1, args.time2, args.time3 = args.times[:3]
    else:
        args.time1, args.time2, args.time3 = 10, 15, 20

    # Launch application
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True) #enable highdpi scaling
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True) #use highdpi icons
    app = PresentationTimerApp(args)
    app.run()


if __name__ == "__main__":
    main()
