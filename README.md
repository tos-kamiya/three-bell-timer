# three-bell-timer

A lightweight timer designed for presentations. It overlays your desktop with a horizontal progress bar that advances in real time.

## Features

### Three-Bell Time Management

- **Bell 1:** Warns that the end is approaching.
- **Bell 2:** Marks the end of the presentation.
- **Bell 3:** Signals the end of the Q&A session.

### Visual Progress Bar

- The bar is divided into _rounded marbles_, one per minute.
  - **Before** a minute elapses: light color
  - **After** a minute elapses: dark color
- Updates every 100 ms for smooth progression.

### Paused State Indicators

- **▶** icon on the left when paused
- Numeric markers for Bell 1, Bell 2, and Bell 3
- Click the ▶ to start/resume without opening the menu

### Display & Position Control

- **Multiple displays:** shows bars on all screens by default
- **`
  --display all
  --display 0
  --display 0,1,2
`** to choose specific screens
- **`
  --pos top
  --pos bottom
`** to set vertical placement
- **Cycle Display Target** menu option to toggle between “all” and each individual screen

### System Tray Icon

- No taskbar icon; use the tray menu for controls:
  - Start/Pause
  - Change bell times
  - Cycle display target
  - Move bar to top or bottom
  - Exit application

## Installation

Recommended: install with **pipx**:

```bash
pipx install git+https://github.com/tos-kamiya/three-bell-timer
```

If you don’t have pipx:
```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Alternatively, install via pip:

```bash
git clone https://github.com/tos-kamiya/three-bell-timer
cd three-bell-timer
pip install .
```

## Usage

Run `3bt` with optional arguments to customize bell times, displays, position, and bar height.

```bash
# Default: bells at 10,15,20 minutes on all displays, top position, 10px height
3bt

# Single time value: all three bells at 12 minutes
3bt 12

# Two values: Bell1=10, Bell2&3=20
3bt 10 20

# Three values: Bell1=10, Bell2=15, Bell3=20 on display 1, bottom, 12px height
3bt 10 15 20 --display 1 --pos bottom --pixel-height 12

# Multiple displays: bars on screens 0 and 2 only
3bt --display 0,2

# Explicit "all"
3bt --display all
```

## License

Distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
