import sys
import time
from typing import List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPen

try:
    from .__about__ import __version__
except ImportError as e:
    __version__ = "(unknown)"
from .utils import interpolate_rgb, find_icon_file, calculate_window_position

TEN_MINUTE_MARK_HEIGHT_SCALE = 1.25
MARGIN_X = 4
PADDING = 2
BORDER_THICKNESS = 1.1
MARKER_BORDER_THICKNESS = 1.8
MARKER_RGBA = (240, 240, 240, 240)
MARKER_DARK_RGBA = (0, 0, 0, 80)
MARKER_BOUNDARY_RGBA = (69, 71, 76, 240)
HINT_RGB = (13, 14, 15)
PRESENTATION_RGB = (0, 117, 153)
TOTAL_RGB = (229, 153, 82)


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
        self.hint_time: int = t1  # min
        self.presentation_end: int = max(t1, t2)  # min
        self.total_minutes: int = max(self.presentation_end, t3)  # min
        self._accum: float = 0.0  # sec
        self._start: float = time.time()  # sec
        self._paused: bool = True

    def tick(self) -> None:
        self.timeUpdated.emit()

    def toggle_pause(self) -> None:
        if self._paused:
            self._start = time.time()
        else:
            self._accum += time.time() - self._start
        self._paused = not self._paused
        self.stateChanged.emit()

    def reset(self) -> None:
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
    def __init__(self, model: TimerModel, running_height: int, position: str):
        super().__init__()
        self.model = model
        self.running_height: int = running_height
        self.position: str = position
        model.timeUpdated.connect(self.update)
        model.stateChanged.connect(self.update)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w, h = self.width() - MARGIN_X * 2, (self.height() if self.model.is_paused else self.running_height)
        marble_width = w / self.model.total_minutes
        rr_size = max(0.0, (h - 2 * PADDING) / 5)
        marker_color = QColor(*MARKER_RGBA)
        marker_boundary_color = QColor(*MARKER_BOUNDARY_RGBA)
        el = self.model.elapsed()
        el = min(el, self.model.total_minutes * 60.0)
        for i in range(self.model.total_minutes):
            x = i * marble_width + MARGIN_X
            marble_height = h if (i + 1) % 10 == 0 else int(h / TEN_MINUTE_MARK_HEIGHT_SCALE)
            y = h - marble_height if self.position == "bottom" else 0
            rect = QRectF(x + PADDING, y + PADDING, marble_width - 2 * PADDING, marble_height - 2 * PADDING)
            base = (
                HINT_RGB
                if i < self.model.hint_time
                else PRESENTATION_RGB if i < self.model.presentation_end else TOTAL_RGB
            )
            light_fill_color = QColor(*interpolate_rgb(base, (255, 255, 255), 0.70), 150)
            dark_fill_color = QColor(*base, 220)
            dark_pen_color = QColor(*base)
            light_pen_color = QColor(*interpolate_rgb(base, (255, 255, 255), 0.70))
            is_last_min = (i + 1) in [self.model.hint_time, self.model.presentation_end, self.model.total_minutes]
            b = BORDER_THICKNESS * 1.5 if self.model.is_paused and is_last_min else BORDER_THICKNESS

            s_sec, e_sec = i * 60, (i + 1) * 60
            if el >= e_sec:
                painter.setPen(QPen(light_pen_color, b))
                painter.setBrush(dark_fill_color)
                painter.drawRoundedRect(rect, rr_size, rr_size)
            elif el < s_sec:
                painter.setPen(QPen(dark_pen_color, b))
                painter.setBrush(light_fill_color)
                painter.drawRoundedRect(rect, rr_size, rr_size)
            else:
                frac = (el - s_sec) / 60.0
                painter.setPen(QPen(dark_pen_color, b))
                painter.setBrush(light_fill_color)
                painter.drawRoundedRect(rect, rr_size, rr_size)

                dw = rect.width() * frac
                clip = QRectF(rect.left(), 0, dw, self.height())
                painter.save()
                painter.setClipRect(clip)
                painter.setPen(QPen(light_pen_color, b))
                painter.setBrush(dark_fill_color)
                painter.drawRoundedRect(rect, rr_size, rr_size)
                painter.restore()

        marble_height = int(h / TEN_MINUTE_MARK_HEIGHT_SCALE)
        y = h - marble_height if self.position == "bottom" else 0

        if el > 0:
            scale = 0.8 if self.model.is_paused else 1.7
            hand_size = max(4.0, (marble_height - 2 * PADDING) * scale)
            hx = w * (el / (self.model.total_minutes * 60)) - hand_size / 2 + MARGIN_X
            if self.model.is_paused or (int(time.time()) % 3) != 0:
                painter.setBrush(marker_color)
                painter.setPen(QPen(marker_boundary_color, MARKER_BORDER_THICKNESS))
            else:
                painter.setBrush(QColor(*MARKER_DARK_RGBA))
                painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(hx, y + (marble_height - hand_size) / 2, hand_size, hand_size))

        if self.model.is_paused:
            s = marble_height - 2 * PADDING
            px = MARGIN_X + PADDING + MARKER_BORDER_THICKNESS
            py = y + PADDING
            tri = QtGui.QPolygonF(
                [
                    QPointF(px + s * 0.3, py + s * 0.15),
                    QPointF(px + s * 0.3, py + s * 0.85),
                    QPointF(px + s * 0.8, py + s * 0.5),
                ]
            )
            painter.setBrush(marker_color)
            painter.setPen(QPen(marker_boundary_color, MARKER_BORDER_THICKNESS))
            painter.drawPolygon(tri)

            font = painter.font()
            font.setPointSizeF(s * 0.7)
            font.setBold(True)
            painter.setFont(font)
            for mark, shadow_rgb in zip(
                [self.model.hint_time, self.model.presentation_end, self.model.total_minutes],
                [HINT_RGB, PRESENTATION_RGB, TOTAL_RGB],
            ):
                painter.setPen(QColor(*shadow_rgb, 80))
                box = QRectF(
                    MARGIN_X - MARKER_BORDER_THICKNESS,
                    y + PADDING,
                    mark * marble_width - (PADDING + MARKER_BORDER_THICKNESS) - MARGIN_X,
                    s,
                )
                painter.drawText(box, Qt.AlignRight | Qt.AlignVCenter, str(mark))
                box = QRectF(
                    MARGIN_X + MARKER_BORDER_THICKNESS,
                    y + PADDING,
                    mark * marble_width - (PADDING + MARKER_BORDER_THICKNESS) - MARGIN_X,
                    s,
                )
                painter.drawText(box, Qt.AlignRight | Qt.AlignVCenter, str(mark))
                painter.setPen(marker_color)
                box = QRectF(
                    MARGIN_X, y + PADDING, mark * marble_width - (PADDING + MARKER_BORDER_THICKNESS) - MARGIN_X, s
                )
                painter.drawText(box, Qt.AlignRight | Qt.AlignVCenter, str(mark))


# ---- Presentation Window ----
class PresentationTimerWindow(QtWidgets.QMainWindow):
    def __init__(self, manager, model: TimerModel, display_index: int, pos: str, height: int):
        super().__init__()
        self.manager = manager
        self.model = model
        self.display_index = display_index
        self.position = pos
        self.margin = 2
        self.paused_h = int(40 * TEN_MINUTE_MARK_HEIGHT_SCALE)
        self.running_h = int(min(self.paused_h, max(height, 10)) * TEN_MINUTE_MARK_HEIGHT_SCALE)
        self.timerBar = TimerBar(model, height, self.position)
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
        self.timerBar.position = self.position

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
        # Load QApplication
        self.app = QtWidgets.QApplication.instance()

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

        parent_window = self.windows[0] if self.windows else None
        dialog = TimeSettingsDialog(
            parent_window, self.model.hint_time, self.model.presentation_end, self.model.total_minutes
        )

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
