# ABOUT #
It's simple clipboard history manager for using with rofi. 

# INSTALL #
```
#!bash
apt-get install python-pyperclip xautomation
git clone https://bitbucket.org/pandozer/rofi-clipboard-manager.git
cd rofi-clipboard-manager
```

Run daemon:
```
#!bash

/path/to/mclip/mclip.py daemon &
```

and bind hotkey: 
```
#!bash
"rofi -modi "clipboard:/path/to/mclip/mclip.py menu" -show clipboard && /path/to/mclip/mclip.py paste"
```

# i3wm EXAMPLE CONFIG

```
#!config

set $mclip /path/to/mclip/mclip.py
bindsym control+shift+v exec rofi -modi "clipboard:$mclip menu" && $mclip paste
exec --no-startup-id $mclip daemon
```

# SETTINGS #

```
#!python

CLIP_LIMIT = 50             # number of clipboard history
HISTORY_FILE = os.environ['HOME'] + '/.clipboard-history.bin'
CLIP_FILE = os.environ['HOME'] + '/.clipboard'
STRING_LIMIT = 100
HELP = '''./mclip.py menu|daemon'''
PASTE = '''keydown Control_L
key v
keyup Control_L
'''                         # your paste key
DAEMON_DELAY = 1
```