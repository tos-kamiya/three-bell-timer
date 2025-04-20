import argparse
import colorsys
import os
import platform
import sys
import shutil
import time
from typing import List, Tuple

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon

try:
    from .__about__ import __version__
except ImportError as e:
    __version__ = "(unknown)"


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


def modify_v(rgb: Tuple[int, int, int], v_add: float) -> Tuple[int, int, int]:
    assert -1.0 <= v_add <= 1.0

    r, g, b = rgb
    assert 0 <= r <= 255
    assert 0 <= g <= 255
    assert 0 <= b <= 255

    rgb_01 = (r / 255, g / 255, b / 255)  # Normalize RGB to 0-1 range
    hsv = colorsys.rgb_to_hsv(*rgb_01)

    new_v = hsv[2] + v_add
    new_hsv = (hsv[0], hsv[1], max(0.0, min(1.0, new_v)))

    new_rgb_01 = colorsys.hsv_to_rgb(*new_hsv)
    new_rgb = int(new_rgb_01[0] * 255), int(new_rgb_01[1] * 255), int(new_rgb_01[2] * 255)

    return new_rgb


class TimeSettingsDialog(QtWidgets.QDialog):
    """Dialog for changing bell times (in minutes)."""

    def __init__(self, parent: QtWidgets.QWidget = None, time1: int = 10, time2: int = 15, time3: int = 20) -> None:
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


class TimerBar(QtWidgets.QWidget):
    """
    A widget that draws each minute as a rounded rectangle ("marble").

    The entire timer is divided into marbles corresponding to the total minutes specified via
    the command line. Each marble is filled with a light color (alpha=80) before the time elapses
    and a dark color (alpha=240) after the time elapses. When the marble is in progress, its left
    side is drawn with the dark color and the right side with the light color using a gradient-like
    effect.

    Colors are set as follows:
      - For minutes 0 to (time1 - 1):          (0, 48, 146)
      - For minutes time1 to (time2 - 1):        (0, 135, 158)
      - For minutes time2 and beyond:           (255, 171, 91)

    In the paused state, a large "▶" icon is drawn on the left, and the markers indicating the times
    (e.g. 10, 15, 20) are displayed at the positions corresponding to Bell 1, Bell 2, and Bell 3.
    """

    def __init__(self, time1: int = 10, time2: int = 15, time3: int = 20, running_bar_display_height: int = 10) -> None:
        super().__init__()
        time2 = max(time1, time2)
        time3 = max(time2, time3)

        self.hint_time: int = time1
        self.presentation_end: int = time2
        self.total_minutes: int = time3
        self.running_bar_display_height: int = running_bar_display_height

        # Timer for updating the display every 100 millisecond
        self.update_timer: QtCore.QTimer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update)
        self.update_timer.start(100)

        # Timing measurement (initially in paused state)
        self._accumulated_time: float = 0.0  # Accumulated seconds until paused
        self._running_start_time: float = time.time()  # Updated on resume
        self._is_paused: bool = True

    def toggle_pause(self) -> None:
        """Toggle between paused and running states."""
        if self._is_paused:
            # Resume: start measuring time again
            self._running_start_time = time.time()
            self._is_paused = False
        else:
            # Pause: accumulate elapsed time and mark as paused
            self._accumulated_time += time.time() - self._running_start_time
            self._is_paused = True

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter: QtGui.QPainter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        total_width: float = self.width()
        # Use full widget height when paused; otherwise, use the running bar height.
        total_height: float = self.height() if self._is_paused else self.running_bar_display_height
        gap: float = 2  # Margin inside each marble
        border_thickness: int = 2
        marble_width: float = total_width / self.total_minutes
        radius: float = (total_height - 2 * gap) / 4
        if radius < 0.5:
            radius = 0.0

        # Calculate elapsed seconds
        elapsed: float
        if self._is_paused:
            elapsed = self._accumulated_time
        else:
            elapsed = self._accumulated_time + (time.time() - self._running_start_time)

        for i in range(self.total_minutes):
            x: float = i * marble_width
            rect: QtCore.QRectF = QtCore.QRectF(x + gap, gap, marble_width - 2 * gap, total_height - 2 * gap)
            # Set base color according to the minute index
            if i < self.hint_time:
                base_color = (0, 48, 146)
            elif i < self.presentation_end:
                base_color = (0, 135, 158)
            else:
                base_color = (255, 171, 91)
            light_color: QtGui.QColor = QtGui.QColor(*modify_v(base_color, 0.3))
            light_color.setAlpha(100 if self._is_paused else 100)
            dark_color: QtGui.QColor = QtGui.QColor(*modify_v(base_color, -0.1))
            dark_color.setAlpha(250 if self._is_paused else 220)

            start_sec: float = i * 60
            end_sec: float = (i + 1) * 60

            painter.setPen(QtCore.Qt.NoPen)
            if elapsed >= end_sec:
                # This marble is completely elapsed
                painter.setBrush(dark_color)
                painter.drawRoundedRect(rect, radius, radius)
            elif elapsed <= start_sec:
                # This marble has not yet started
                painter.setBrush(light_color)
                painter.drawRoundedRect(rect, radius, radius)
            else:
                # In-progress: left side is dark, right side is light
                fraction: float = (elapsed - start_sec) / 60.0
                painter.setBrush(light_color)
                painter.drawRoundedRect(rect, radius, radius)
                dark_width: float = rect.width() * fraction
                dark_rect: QtCore.QRectF = QtCore.QRectF(rect.left(), rect.top(), dark_width, rect.height())
                painter.save()
                painter.setClipRect(dark_rect)  # Clip to maintain rounded corners
                painter.setBrush(dark_color)
                painter.drawRoundedRect(rect, radius, radius)
                painter.restore()

                # Draw an animated vertical indicator at the boundary.
                # When the timer is running, cycle through 1, 2, and 3 markers.
                # When paused, use a fixed single marker.
                n: int = (int(time.time()) % 3) + 1 if not self._is_paused else 1
                marker_size: float = (total_height - 2 * gap) * 0.75
                spacing: float = 1
                hand_x: float = rect.left() + dark_width - marker_size / 2
                hand_color: QtGui.QColor = QtGui.QColor(255, 255, 255)
                painter.setBrush(hand_color)
                painter.setPen(QtCore.Qt.NoPen)
                for j in range(n):
                    x_i: float = hand_x + j * (marker_size + spacing)
                    line_rect: QtCore.QRectF = QtCore.QRectF(
                        x_i, (total_height - marker_size) / 2, marker_size, marker_size
                    )
                    painter.drawEllipse(line_rect)

            # When paused, draw a border around each marble with opaque color
            if self._is_paused:
                border_color: QtGui.QColor = QtGui.QColor(*base_color)
                border_color.setAlpha(240)
                pen: QtGui.QPen = QtGui.QPen(border_color)
                pen.setWidth(border_thickness)
                painter.setPen(pen)
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawRoundedRect(rect, radius, radius)

        # When paused, draw a large "▶" icon and bell markers (the numbers).
        if self._is_paused:
            icon_area: float = total_height  # Square region for the icon
            icon_rect: QtCore.QRectF = QtCore.QRectF(0, 0, icon_area, icon_area)
            triangle = QtGui.QPolygonF()
            triangle.append(QtCore.QPointF(icon_rect.left() + icon_rect.width() * 0.3, icon_rect.top() + icon_rect.height() * 0.2))
            triangle.append(QtCore.QPointF(icon_rect.left() + icon_rect.width() * 0.3, icon_rect.top() + icon_rect.height() * 0.8))
            triangle.append(QtCore.QPointF(icon_rect.left() + icon_rect.width() * 0.8, icon_rect.top() + icon_rect.height() * 0.5))
            painter.setPen(QtCore.Qt.NoPen)
            marker_color = QtGui.QColor(255, 255, 255)
            marker_color.setAlpha(180)
            painter.setBrush(marker_color)
            painter.drawPolygon(triangle)

            font: QtGui.QFont = painter.font()
            font.setPointSizeF(total_height * 0.5)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(marker_color)
            bell_markers: List[int] = [self.hint_time, self.presentation_end, self.total_minutes]
            for mark in bell_markers:
                text_box_width = marble_width * 3
                rect_marker: QtCore.QRectF = QtCore.QRectF(mark * marble_width - text_box_width - (2 * gap + border_thickness), 0, text_box_width, total_height)
                painter.drawText(rect_marker, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, str(mark))


def add_menu_items(menu: QtWidgets.QMenu):
    resume_action = menu.addAction("Resume / Pause")
    menu.addSeparator()
    move_top_action = menu.addAction("Move to Top")
    move_bottom_action = menu.addAction("Move to Bottom")
    move_next_disp_action = menu.addAction("Move to Next Display")
    menu.addSeparator()
    change_times_action = menu.addAction("Change Bell Times")
    menu.addSeparator()
    exit_action = menu.addAction("Exit")
    return resume_action, move_top_action, move_bottom_action, move_next_disp_action, change_times_action, exit_action


class PresentationTimerWindow(QtWidgets.QMainWindow):
    """
    A transparent window that displays the timer bar (a series of marbles across the full width).

    The window's width is set with margins from the desktop width. The window is positioned at the
    top or bottom of the specified display's available area (default is top). When paused, the window's
    height is larger; when running, the height is reduced. Both left-click and right-click display the same
    menu, except that clicking within the "▶" icon area (at the left, approximately the paused height) resumes
    the timer without showing the menu.
    """

    def __init__(
        self, time1: int, time2: int, time3: int, display_index: int, pos_spec: str, pixel_height: int
    ) -> None:
        super().__init__()
        self.time1: int = time1
        self.time2: int = time2
        self.time3: int = time3
        self.display_index: int = display_index  # 0-indexed
        self.position: str = pos_spec  # "top" or "bottom"
        self.margin: int = 2  # Margin on all sides
        self.paused_height: int = 40  # Window height when paused
        self.running_height: int = min(self.paused_height, max(pixel_height, 10))  # Window height when running
        self.running_bar_display_height: int = pixel_height
        self.setup_window()

        # Timer to adjust the window position periodically (every 3 seconds)
        self.adjust_timer: QtCore.QTimer = QtCore.QTimer(self)
        self.adjust_timer.timeout.connect(self.adjustPosition)
        self.adjust_timer.start(3000)

    def setup_window(self) -> None:
        self.setWindowTitle("Presentation Timer")
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # Set the timer bar widget as the central widget
        self.timerBar: TimerBar = TimerBar(self.time1, self.time2, self.time3, self.running_bar_display_height)
        self.setCentralWidget(self.timerBar)
        self.adjustPosition()

    def adjustPosition(self) -> None:
        """
        Reposition the window based on the available area of the specified display.
        The window's width is set with margins, and its height depends on whether the timer is paused.
        """
        screens = QtWidgets.QApplication.screens()
        target_screen = screens[self.display_index] if self.display_index < len(screens) else screens[0]
        available: QtCore.QRect = target_screen.availableGeometry()
        new_height: int = self.paused_height if self.timerBar._is_paused else self.running_height
        x: int = available.left() + self.margin
        width: int = available.width() - 2 * self.margin
        y: int = (
            available.top() + self.margin if self.position == "top" else available.bottom() - new_height - self.margin
        )
        self.setGeometry(x, y, width, new_height)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Displays a menu on left/right click, except when in paused state and clicking in the "▶" icon area
        (left side, approximately within the paused height), in which case the timer is resumed directly.

        Menu items:
          - Resume / Pause
          - Move to Top
          - Move to Bottom
          - Move to Next Display
          - Exit
        """
        if event.button() == QtCore.Qt.LeftButton:
            # If paused and clicking in the "▶" icon area, resume without showing the menu
            if self.timerBar._is_paused and event.pos().x() < self.paused_height:
                self.timerBar.toggle_pause()  # Resume
                # Recalculate desktop size and adjust window position on resume
                self.adjustPosition()
                return

        if event.button() in (QtCore.Qt.LeftButton, QtCore.Qt.RightButton):
            pos = event.globalPos()
            menu: QtWidgets.QMenu = QtWidgets.QMenu(self)

            (
                resume_action,
                move_top_action,
                move_bottom_action,
                move_next_disp_action,
                change_times_action,
                exit_action,
            ) = add_menu_items(menu)
            action = menu.exec_(pos)
            if action == resume_action:
                self.timerBar.toggle_pause()
                self.adjustPosition()
            elif action == move_top_action:
                self.position = "top"
                self.adjustPosition()
            elif action == move_bottom_action:
                self.position = "bottom"
                self.adjustPosition()
            elif action == move_next_disp_action:
                screens: List[QtGui.QScreen] = QtWidgets.QApplication.screens()
                if len(screens) > 1:
                    self.display_index = (self.display_index + 1) % len(screens)
                self.adjustPosition()
            elif action == change_times_action:
                self.update_time_settings()
            elif action == exit_action:
                QtWidgets.QApplication.quit()

    def update_time_settings(self) -> None:
        dialog = TimeSettingsDialog(self, self.time1, self.time2, self.time3)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        new_time1 = dialog.spin1.value()
        new_time2 = dialog.spin2.value()
        new_time3 = dialog.spin3.value()

        # Update the timer settings in the main window and timer bar.
        self.time1, self.time2, self.time3 = new_time1, new_time2, new_time3
        self.timerBar.hint_time = new_time1
        self.timerBar.presentation_end = new_time2
        self.timerBar.total_minutes = new_time3

        # Reinitialize the timer (reset elapsed time and pause)
        self.timerBar._accumulated_time = 0.0
        self.timerBar._running_start_time = time.time()
        self.timerBar._is_paused = True
        self.adjustPosition()


def main() -> None:
    parser = argparse.ArgumentParser(description="Presentation Timer")
    parser.add_argument(
        "times",
        type=int,
        nargs="*",
        help="Time settings: provide one value for Bell1=Bell2=Bell3, two values for Bell1 and Bell2=Bell3, or three values for each bell separately",
    )
    parser.add_argument("--display", "-d", type=int, default=0, help="Display index to use (0-indexed)")
    parser.add_argument(
        "--pos",
        "-p",
        choices=["top", "bottom"],
        default="top",
        help="Window position relative to the screen ('top' or 'bottom')",
    )
    parser.add_argument(
        "--pixel-height", "-s", type=int, default=10, help="Height of the timer bar in pixels (default: 10)"
    )
    parser.add_argument(
        "--generate-desktop", action="store_true",
        help="Generate a .desktop file in the current directory"
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    args = parser.parse_args()

    if args.generate_desktop:
        generate_desktop_file()
        sys.exit(0)

    # Determine time settings based on the number of values provided
    if len(args.times) == 1:
        time1 = time2 = time3 = args.times[0]
    elif len(args.times) == 2:
        time1 = args.times[0]
        time2 = time3 = args.times[1]
    elif len(args.times) >= 3:
        time1, time2, time3 = args.times[:3]
    else:
        time1, time2, time3 = 10, 15, 20

    # Set up application object and main window
    app = QtWidgets.QApplication(sys.argv)
    icon_path = find_icon_file("icon.ico")
    if icon_path is not None:
        app.setWindowIcon(QIcon(icon_path))

    mainWindow = PresentationTimerWindow(time1, time2, time3, args.display, args.pos, args.pixel_height)
    mainWindow.show()

    # Create the system tray icon using the main window as the parent
    tray_icon: QtWidgets.QSystemTrayIcon = QtWidgets.QSystemTrayIcon(mainWindow)
    icon_path = find_icon_file("icon.ico")
    if icon_path is not None:
        tray_icon.setIcon(QtGui.QIcon(icon_path))
    else:
        tray_icon.setIcon(mainWindow.windowIcon())

    # Set up the tray menu with the desired actions
    tray_menu: QtWidgets.QMenu = QtWidgets.QMenu()
    resume_action, move_top_action, move_bottom_action, move_next_disp_action, change_times_action, exit_action = (
        add_menu_items(tray_menu)
    )
    tray_icon.setContextMenu(tray_menu)

    # Connect the actions to corresponding handlers.
    resume_action.triggered.connect(lambda: (mainWindow.timerBar.toggle_pause(), mainWindow.adjustPosition()))
    move_top_action.triggered.connect(lambda: (setattr(mainWindow, "position", "top"), mainWindow.adjustPosition()))
    move_bottom_action.triggered.connect(
        lambda: (setattr(mainWindow, "position", "bottom"), mainWindow.adjustPosition())
    )
    move_next_disp_action.triggered.connect(
        lambda: (
            setattr(
                mainWindow, "display_index", (mainWindow.display_index + 1) % len(QtWidgets.QApplication.screens())
            ),
            mainWindow.adjustPosition(),
        )
    )
    change_times_action.triggered.connect(lambda: (mainWindow.update_time_settings(), mainWindow.adjustPosition()))
    exit_action.triggered.connect(QtWidgets.QApplication.quit)

    # Show the system tray icon
    tray_icon.show()

    # Start event loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
