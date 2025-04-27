import argparse
import sys

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QIcon

from .utils import generate_desktop_file, find_icon_file
from .three_bell_timer import TimeSettingsDialog, PresentationTimerApp


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
    parser.add_argument(
        "--pos", "-p", choices=["top", "bottom"], default="top", help="window position on screen (default: 'top')"
    )
    parser.add_argument(
        "--pixel-height", "-s", type=int, default=12, help="height of the running timer bar (default: 12)"
    )
    parser.add_argument("--prompt-times", action="store_true", help="open modal dialog to specify bell times at start")
    parser.add_argument("--generate-desktop", action="store_true", help="output a .desktop file and exit")
    args = parser.parse_args()

    if args.generate_desktop:
        generate_desktop_file()
        sys.exit(0)

    # Qt setting
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)  # enable highdpi scaling
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)  # use highdpi icons

    app = QtWidgets.QApplication(sys.argv)
    icon_path = find_icon_file("icon.ico")
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    if args.prompt_times:
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
    app = PresentationTimerApp(args)
    app.run()


if __name__ == "__main__":
    main()
