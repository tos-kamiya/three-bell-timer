# presen-time-bar

A lightweight, transparent PyQt5-based timer designed for presentations. It displays a horizontal progress bar that overlays your desktop.

## Features

Time management for the so-called "Three Bells."

Typically, the first bell notifies the presenter that the end is near, the second bell marks the end of the presentation, and the third bell signals the end of the Q&A session.

**Visual Progress Bar:**  

The timer bar is divided into rounded rectangles (marble), one per minute.
- Before a minute elapses, each marble is drawn with a light color.
- After the minute has elapsed, it is drawn in a dark color.
The timer bar appears at the top of the screen and updates periodically.

**Paused State Indicators:**  

When the timer starts, it is paused:
- A large “▶” icon is shown on the left side of the bar.
- The predetermined marker times (Bell 1, Bell 2, and Bell 3) are displayed in the bar.

**Menu Options:**  

Clicking on the “▶” icon resumes (or starts) the timer.  
The right-click menu allows you to change the timer's position on the screen or move it to another display.

## Installation

Install **presen-time-bar** using pipx:

```bash
pipx install git+https://github.com/tos-kamiya/presen-time-bar
```

*Note: pipx is recommended for installing Python CLI applications in isolated environments. If you don't have pipx installed, you can get it via:*

```bash
python3 -m pip install pipx
python3 -m pipx ensurepath
```

Alternatively, you can install with:

```bash
git clone https://github.com/tos-kamiya/presen-time-bar
pip install .
```

## Usage

Run the application from the command line with customizable options. You can set the time for the bells, the display index, the position (top or bottom), and the pixel height of the timer bar.

### Command-line Examples

- **Default settings (10, 15, 20 minutes):**
  ```bash
  presen-time-bar
  ```

- **One time value (Bell 1 only):**
  ```bash
  presen-time-bar 12
  ```

- **Two time values (Bell 1 uses the first value; Bells 2 use the second):**
  ```bash
  presen-time-bar 10 20
  ```

- **Three time values:**
  ```bash
  presen-time-bar 10 15 20
  ```

- **Additional options (e.g., display index, position, and pixel height):**
  ```bash
  presen-time-bar 10 15 20 --display 1 --pos bottom --pixel-height 12
  ```

## License

`presen-time-bar` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
