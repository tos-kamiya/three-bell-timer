```sh
inkscape icon.svg --export-type=png --export-filename=icon64.png --export-width=64 --export-height=64
inkscape icon.svg --export-type=png --export-filename=icon128.png --export-width=128 --export-height=128
inkscape icon.svg --export-type=png --export-filename=icon256.png --export-width=256 --export-height=256
convert icon256.png -define icon:auto-resize icon.ico
```

