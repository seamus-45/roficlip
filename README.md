# About #
Clipboard history manager designed for using with [Rofi](https://davedavenport.github.io/rofi/).

# Features #
* Show runtime (ring) clipboard history.
* Show/Create/Delete persistent notes from clipboard.
* Define and use actions with clipboard contents.
* Desktop notifications via D-Bus.

# Requirements #
* [pygobject](https://pypi.org/project/PyGObject/)
* [pyyaml](https://pypi.org/project/PyYAML/)
* [pyxdg](https://pypi.org/project/pyxdg/)
* [docopt](https://pypi.org/project/docopt/)
* [notify2](https://pypi.org/project/notify2/)

# Installation #
* Install requirements via your favorite package manager.
* Clone this repository to preferred place.
* Make link to roficlip.py and place it to directory listed in $PATH e.g.: `ln -s ~/bin/apps/roficlip/roficlip.py ~/bin`

# Usage #
Run clipboard watcher:
```bash
roficlip.py --daemon &
```

Read the help:
```bash
roficlip.py --help
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
  ring_size: 20                 # maximum clips count.
  preview_width: 100            # maximum preview width for rofi.
  newline_char: '¬'             # any character for using in preview as new line marker.
  comment_char: '©'
  notify: True                  # allow using desktop notifications.
  notify_timeout: 1             # notification timeout in seconds.
  show_comments_first: False    # if using persistent notes for command shortcuts followed by '#' comment.

actions:
  'open url via mpv player': 'mpv --geometry=720x405-20-20 %s' # %s will be replaced with current clipboard content.
  'add persistent clip': 'roficlip.py --add' # save current clipboard in persistent history.
  'remove persistent clip': 'roficlip.py --remove' # remove current clipboard from persistent history.
  'clear clipboard': 'roficlip.py --clear' # clear clipboard history.
```
