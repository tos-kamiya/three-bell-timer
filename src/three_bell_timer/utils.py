import colorsys
import os
import platform
import shutil
import sys
from typing import Optional, Tuple

from PyQt5 import QtWidgets
from PyQt5.QtCore import QPoint, QSize


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
