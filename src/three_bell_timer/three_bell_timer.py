import argparse
import colorsys
import os
import platform
import shutil
import sys
import time
from typing import List, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QPoint, QPointF, QRectF, QSize, Qt
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


def calculate_window_position(cursor_pos: QPoint, window_size: QSize, margin: int = 10) -> QPoint:
    """Calculates an appropriate top-left position for a window near the cursor.

    This function attempts to position a window close to the provided cursor
    position (initially trying bottom-right). It ensures the entire window
    remains visible within the available geometry of the screen containing
    the cursor, respecting a minimum margin from the screen edges.

    Args:
        cursor_pos: The current global position of the mouse cursor (QtGui.QCursor.pos()).
        window_size: The size (QSize) of the window to be positioned.
                     Using dialog.sizeHint() before showing is a common way to get an estimate.
        margin: The minimum space (in pixels) to keep between the window and the screen edges.

    Returns:
        The calculated top-left QPoint for the window. Returns a default position
        (e.g., top-left corner with margin) if screen detection fails.
    """
    # --- Determine the screen containing the cursor ---
    screen = None
    # Use QApplication.screenAt() if available (PyQt >= 5.14 recommended)
    if hasattr(QtWidgets.QApplication, "screenAt"):
        screen = QtWidgets.QApplication.screenAt(cursor_pos)

    # Fallback for older PyQt versions or if screenAt fails
    if not screen:
        screen_number = QtWidgets.QApplication.desktop().screenNumber(cursor_pos)
        if screen_number != -1:
            try:
                screen = QtWidgets.QApplication.screens()[screen_number]
            except IndexError:
                print(f"Warning: Screen number {screen_number} out of range.", file=sys.stderr)
                screen = None  # Ensure screen is None if index is bad

    # Ultimate fallback to the primary screen if no screen could be determined
    if not screen:
        screen = QtWidgets.QApplication.primaryScreen()

    # If still no screen (highly unlikely unless in a very unusual setup), return a default
    if not screen:
        print("Error: Could not determine any screen for positioning.", file=sys.stderr)
        return QPoint(margin, margin)  # Default to top-left corner

    screen_geometry = screen.availableGeometry()  # Use availableGeometry to avoid docks/taskbars

    # --- Calculate initial target position ---
    # Start by trying to place the window bottom-right of the cursor
    target_x = cursor_pos.x() + margin // 2  # Small offset from cursor
    target_y = cursor_pos.y() + margin // 2

    # --- Adjust position to fit within screen bounds ---

    # Adjust horizontally
    screen_right_limit = screen_geometry.right() - margin
    screen_left_limit = screen_geometry.left() + margin

    if target_x + window_size.width() > screen_right_limit:
        # If it overflows the right edge, try placing it to the left of the cursor
        target_x = cursor_pos.x() - window_size.width() - margin // 2
        # If it now overflows the left edge, clamp it to the left edge
        if target_x < screen_left_limit:
            target_x = screen_left_limit
    elif target_x < screen_left_limit:
        # If the initial position was already too far left, clamp it to the left edge
        target_x = screen_left_limit

    # Adjust vertically
    screen_bottom_limit = screen_geometry.bottom() - margin
    screen_top_limit = screen_geometry.top() + margin

    if target_y + window_size.height() > screen_bottom_limit:
        # If it overflows the bottom edge, try placing it above the cursor
        target_y = cursor_pos.y() - window_size.height() - margin // 2
        # If it now overflows the top edge, clamp it to the top edge
        if target_y < screen_top_limit:
            target_y = screen_top_limit
    elif target_y < screen_top_limit:
        # If the initial position was already too far up, clamp it to the top edge
        target_y = screen_top_limit

    return QPoint(target_x, target_y)


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
        gap, border = 2, 1.3
        mw = w / self.model.total_minutes
        r = max(0.0, (h - 2 * gap) / 4)
        mc = QColor(240, 240, 240)
        mc.setAlpha(240)
        base0 = (0, 53, 153)
        el = self.model.elapsed()
        hand_rect = None
        for i in range(self.model.total_minutes):
            x = i * mw
            rect = QRectF(x + gap, gap, mw - 2 * gap, h - 2 * gap)
            if i < self.model.hint_time:
                base = base0
            elif i < self.model.presentation_end:
                base = (0, 125, 145)
            else:
                base = (229, 153, 82)
            lc = QColor(*base)
            lc.setAlpha(80)
            dc = QColor(*base)
            bc = QColor(*modify_hsv(base, s=0.3))

            s_sec, e_sec = i * 60, (i + 1) * 60
            if el >= e_sec:
                painter.setPen(QPen(bc, border))
                painter.setBrush(dc)
                painter.drawRoundedRect(rect, r, r)
            elif el < s_sec:
                painter.setPen(QPen(bc, border))
                painter.setBrush(lc)
                painter.drawRoundedRect(rect, r, r)
            else:
                frac = (el - s_sec) / 60.0
                painter.setPen(QPen(bc, 1.3))
                painter.setBrush(lc)
                painter.drawRoundedRect(rect, r, r)
                dw = rect.width() * frac
                clip = QRectF(rect.left(), rect.top(), dw, rect.height())
                painter.save()
                painter.setClipRect(clip)
                painter.setBrush(dc)
                painter.drawRoundedRect(rect, r, r)
                painter.restore()

                if el > 0 and (self.model.is_paused or (int(time.time()) % 2) == 1):
                    hand_rect = rect

        if hand_rect is not None:
            rect = hand_rect
            ms = max(4.0, (h - 2 * gap) * 0.72)
            hx = rect.left() + dw - ms / 2
            painter.setBrush(mc)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(hx, (h - ms) / 2, ms, ms))

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
                box = QRectF(0, 0, mark * mw - (gap + border), h)
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
        app_icon = find_icon_file("icon.ico")
        if app_icon:
            qicon = QtGui.QIcon(app_icon)
            self.app.setWindowIcon(qicon)
        else:
            qicon = self.app.windowIcon()
        self.tray.setIcon(qicon)

        menu = QtWidgets.QMenu()
        cyc = menu.addAction("Cycle Display Target")
        cyc.triggered.connect(self.cycle_display_target)
        menu.addSeparator()
        resume = menu.addAction("Resume / Pause")
        resume.triggered.connect(self.model.toggle_pause)
        change = menu.addAction("Change Bell Times")
        change.triggered.connect(self.update_time_settings)
        menu.addSeparator()
        exit_a = menu.addAction("Exit")
        exit_a.triggered.connect(QtWidgets.QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def update_time_settings(self):
        cursor_pos = QtGui.QCursor.pos()

        # Create the dialog instance (without parent for independent positioning)
        dialog = TimeSettingsDialog(None, self.model.hint_time, self.model.presentation_end, self.model.total_minutes)

        # Get the estimated size of the dialog
        # Calling adjustSize() or layout().activate() might give a more accurate size hint
        # before showing, but sizeHint() is often sufficient.
        dialog_size = dialog.sizeHint()

        # Calculate the optimal position using the helper function
        optimal_pos = calculate_window_position(cursor_pos, dialog_size, margin=10)  # Pass cursor pos and dialog size

        # Move the dialog to the calculated position
        dialog.move(optimal_pos)

        # Execute the dialog and process the result
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            t1 = dialog.spin1.value()
            t2 = dialog.spin2.value()
            t3 = dialog.spin3.value()
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
    parser.add_argument("--prompt-times", action="store_true", help="open modal dialog to specify bell times at start")
    parser.add_argument("--generate-desktop", action="store_true", help="output a .desktop file and exit")
    args = parser.parse_args()

    if args.generate_desktop:
        generate_desktop_file()
        sys.exit(0)

    if args.prompt_times:
        app = QtWidgets.QApplication(sys.argv)

        # Open dialog to specify bell times
        dialog = TimeSettingsDialog(
            None, getattr(args, "time1", 10), getattr(args, "time2", 15), getattr(args, "time3", 20)
        )
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            sys.exit(0)

        args.time1 = dialog.spin1.value()
        args.time2 = dialog.spin2.value()
        args.time3 = dialog.spin3.value()

        app = None
    else:
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
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)  # enable highdpi scaling
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)  # use highdpi icons
    app = PresentationTimerApp(args)
    app.run()


if __name__ == "__main__":
    main()
