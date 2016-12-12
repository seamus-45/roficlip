# About #
It's clipboard history manager for using with [Rofi](https://davedavenport.github.io/rofi/). 

# Features #
* Show runtime (ring) clipboard history.
* Show/Add/Remove persistent clipboard history.
* Define and use actions with clipboard contents.
* Desktop notifications via libnotify.

# Requirements #
* [pygobject](https://wiki.gnome.org/Projects/PyGObject)
* [pygtk](http://www.pygtk.org/)
* [pyaml](https://pypi.python.org/pypi/PyYAML)
* [notify-python](http://www.galago-project.org/news/index.php)
* [pyxdg](https://cgit.freedesktop.org/xdg/pyxdg/)
* [docopt](https://pypi.python.org/pypi/docopt)

# Installation #
* Install requirements via your favorite package manager.
* Clone this repository to preferred place.
* Make link to roficlip.py and place it to directory listed in $PATH e.g.: `ln -s ~/bin/apps/roficlip/roficlip.py ~/bin`

# Usage #
Run daemon:
```bash
roficlip.py --daemon &
```

Bind hotkey (combined mode): 
```bash
rofi -modi "clipboard:roficlip.py --show,persistent:roficlip.py --show --persistent,actions:roficlip.py --show --actions" -show clipboard
```
or (single mode)
```bash
rofi -modi "clipboard:roficlip.py --show" -show clipboard
```

# Settings #
Yaml config placed in `$XDG_CONFIG_HOME/roficlip/settings` Example:
```yaml
settings:
  ring_size: 20        # maximum clips count.
  preview_width: 100   # maximum preview width for rofi.
  newline_char: '¬'    # any character for using in preview as new line marker.
  notify: True         # allow using desktop notifications.
  notify_timeout: 1    # notification timeout.

actions:
  'open url via mpv player': 'mpv --geometry=720x405-20-20 %s' # %s will be replaced with current clipboard content.
  'add persistent clip': 'roficlip.py -q --add' # save current clipboard as persistent.
  'remove persistent clip': 'roficlip.py -q --remove' # remove current clipboard from persistent.
```
Please see help: `roficlip.py --help` for all command line switches.
