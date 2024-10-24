#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rofi clipboard manager
Usage:
    roficlip.py --daemon [-q | --quiet]
    roficlip.py --show [--persistent | --actions] [<item>] [-q | --quiet]
    roficlip.py --add [-q | --quiet]
    roficlip.py --remove [-q | --quiet]
    roficlip.py --edit
    roficlip.py (-h | --help)
    roficlip.py (-v | --version)

Arguments:
    <item>          Selected item passed by Rofi on second script run.
                    Used with actions as index for dict.

Commands:
    --daemon        Run clipboard manager daemon.
    --show          Show clipboard history.
    --persistent    Select to show persistent history.
    --actions       Select to show actions defined in config.
    --add           Add current clipboard to persistent storage.
    --remove        Remove current clipboard from persistent storage.
    --edit          Edit persistent storage with text editor.
    -q, --quiet     Do not notify, even if notification enabled in config.
    -h, --help      Show this screen.
    -v, --version   Show version.

"""
import errno
import os
import sys
import stat
import struct
from subprocess import Popen, DEVNULL
from tempfile import NamedTemporaryFile

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk, GLib
except ImportError:
    raise

import yaml
from docopt import docopt
from xdg import BaseDirectory

try:
    import notify2
except ImportError:
    pass


# Used for injecting hidden index for menu rows. Simulate dmenu behavior.
# See rofi-script.5 for details
ROFI_INFO = b'\0info\x1f'


class ClipboardManager():
    def __init__(self):
        # Init databases and fifo
        name = 'roficlip'
        self.ring_db = '{0}/{1}'.format(BaseDirectory.save_data_path(name), 'ring.db')
        self.persist_db = '{0}/{1}'.format(BaseDirectory.save_data_path(name), 'persistent.db')
        self.fifo_path = '{0}/{1}.fifo'.format(BaseDirectory.get_runtime_dir(strict=False), name)
        self.config_path = '{0}/settings'.format(BaseDirectory.save_config_path(name))
        if not os.path.isfile(self.ring_db):
            open(self.ring_db, "a+").close()
        if not os.path.isfile(self.persist_db):
            open(self.persist_db, "a+").close()
        if (
            not os.path.exists(self.fifo_path) or
            not stat.S_ISFIFO(os.stat(self.fifo_path).st_mode)
        ):
            os.mkfifo(self.fifo_path)
        self.fifo = os.open(self.fifo_path, os.O_RDONLY | os.O_NONBLOCK)

        # Init clipboard and read databases
        self.cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.ring = self.read(self.ring_db)
        self.persist = self.read(self.persist_db)

        # Load settings
        self.load_config()

        # Init notifications
        if self.cfg['notify'] and 'notify2' in sys.modules:
            self.notify = notify2
            self.notify.init(name)
        else:
            self.cfg['notify'] = False

    def daemon(self):
        """
        Clipboard Manager daemon.
        """
        GLib.timeout_add(300, self.cb_watcher)
        GLib.timeout_add(300, self.fifo_watcher)
        Gtk.main()

    def cb_watcher(self):
        """
        Callback function.
        Watch clipboard and write changes to ring database.
        Must return "True" for continuous operation.
        """
        clip = self.cb.wait_for_text()
        if self.sync_items(clip, self.ring):
            self.ring = self.ring[0:self.cfg['ring_size']]
            self.write(self.ring_db, self.ring)
        return True

    def fifo_watcher(self):
        """
        Callback function.
        Copy contents from fifo to clipboard.
        Must return "True" for continuous operation.
        """
        try:
            fifo_in = os.read(self.fifo, 65536)
        except OSError as err:
            if err.errno == errno.EAGAIN or err.errno == errno.EWOULDBLOCK:
                fifo_in = None
            else:
                raise
        if fifo_in:
            self.cb.set_text(fifo_in.decode('utf-8'), -1)
            self.notify_send('Copied to the clipboard.')
        return True

    def sync_items(self, clip, items):
        """
        Sync clipboard contents with specified items dict when needed.
        Return "True" if dict modified, otherwise "False".
        """
        if clip and (not items or clip != items[0]):
            if clip in items:
                items.remove(clip)
            items.insert(0, clip)
            return True
        return False

    def copy_item(self, index, items):
        """
        Writes to fifo item that should be copied to clipboard.
        """
        with open(self.fifo_path, "w") as file:
            file.write(items[index])
            file.close()

    def show_items(self, items):
        """
        Format and show contents of specified items dict (for rofi).
        """
        for index, clip in enumerate(items):
            if args['--actions']:
                print(clip)
            else:
                clip = clip.replace('\n', self.cfg['newline_char'])
                # Move text after last '#'to beginning of string
                if args['--persistent'] and self.cfg['show_comments_first'] and '#' in clip:
                    # Save index of last '#'
                    idx = clip.rfind('#')
                    # Format string
                    clip = '{}{} ➜ {}'.format(self.cfg['comment_char'], clip[idx+1:], clip[:idx])
                # Truncate text to preview width setting
                preview = clip[0:self.cfg['preview_width']]
                print('{}{}{}'.format(preview, ROFI_INFO.decode('utf-8'), index))

    def persistent_add(self):
        """
        Add current clipboard to persistent storage.
        """
        clip = self.cb.wait_for_text()
        if self.sync_items(clip, self.persist):
            self.write(self.persist_db, self.persist)
            self.notify_send('Added to persistent.')

    def persistent_remove(self):
        """
        Remove current clipboard from persistent storage.
        """
        clip = self.cb.wait_for_text()
        if clip and clip in self.persist:
            self.persist.remove(clip)
            self.write(self.persist_db, self.persist)
            self.notify_send('Removed from persistent.')

    def persistent_edit(self):
        """
        Edit persistent storage with text editor.
        New line char will be used as separator.
        """
        editor = os.getenv('EDITOR', default='vi')
        if self.persist and editor:
            try:
                tmp = NamedTemporaryFile(mode='w+')
                for clip in self.persist:
                    clip = '{}\n'.format(clip.replace('\n', self.cfg['newline_char']))
                    tmp.write(clip)
                tmp.flush()
            except IOError as e:
                print("I/O error({0}): {1}".format(e.errno, e.strerror))
            else:
                proc = Popen([editor, tmp.name], stdout=DEVNULL, stderr=DEVNULL)
                ret = proc.wait()
                if ret == 0:
                    tmp.seek(0, 0)
                    clips = tmp.read().splitlines()
                    if clips:
                        self.persist = []
                        for clip in clips:
                            clip = clip.replace('\n', '')
                            clip = clip.replace(self.cfg['newline_char'], '\n')
                            self.persist.append(clip)
                        self.write(self.persist_db, self.persist)
            finally:
                tmp.close()

    def do_action(self, item):
        """
        Run selected action on clipboard contents.
        """
        clip = self.cb.wait_for_text()
        params = self.actions[item].split(' ')
        while '%s' in params:
            params[params.index('%s')] = clip
        proc = Popen(params, stdout=DEVNULL, stderr=DEVNULL)
        ret = proc.wait()
        if ret == 0:
            self.notify_send(item)

    def notify_send(self, text):
        """
        Show desktop notification.
        """
        if self.cfg['notify']:
            n = self.notify.Notification("Roficlip", text)
            n.timeout = self.cfg['notify_timeout'] * 1000
            n.show()

    def read(self, fd):
        """
        Helper function. Binary reader.
        """
        result = []
        with open(fd, "rb") as file:
            bytes_read = file.read(4)
            while bytes_read:
                chunksize = struct.unpack('>i', bytes_read)[0]
                bytes_read = file.read(chunksize)
                result.append(bytes_read.decode('utf-8'))
                bytes_read = file.read(4)
        return result

    def write(self, fd, items):
        """
        Helper function. Binary writer.
        """
        with open(fd, 'wb') as file:
            for item in items:
                item = item.encode('utf-8')
                file.write(struct.pack('>i', len(item)))
                file.write(item)

    def load_config(self):
        """
        Read config if exists, and/or provide defaults.
        """
        # default settings
        settings = {
            'settings': {
                'ring_size': 20,
                'preview_width': 100,
                'newline_char': '¬',
                'comment_char': '©',
                'notify': True,
                'notify_timeout': 1,
                'show_comments_first': False,
            },
            'actions': {}
        }
        if os.path.isfile(self.config_path):
            with open(self.config_path, "r") as file:
                config = yaml.safe_load(file)
                for key in {'settings', 'actions'}:
                    if key in config:
                        settings[key].update(config[key])
        self.cfg = settings['settings']
        self.actions = settings['actions']


if __name__ == "__main__":
    cm = ClipboardManager()
    args = docopt(__doc__, version='0.5')
    if args['--quiet']:
        cm.cfg['notify'] = False
    if args['--daemon']:
        cm.daemon()
    elif args['--add']:
        cm.persistent_add()
    elif args['--remove']:
        cm.persistent_remove()
    elif args['--edit']:
        cm.persistent_edit()
    elif args['--show']:
        # Parse variables passed from rofi. See rofi-script.5 for details.
        # We get index from selected row here.
        if os.getenv('ROFI_INFO') is not None:
            index = int(os.getenv('ROFI_INFO'))
        elif args['<item>'] is not None:
            index = args['<item>']
        else:
            index = None
        # Show contents on first run
        if index is None:
            cm.show_items(cm.actions if args['--actions'] else cm.persist if args['--persistent'] else cm.ring)
        # Do actions on second run
        else:
            if args['--actions']:
                cm.do_action(index)
            else:
                cm.copy_item(index, cm.persist if args['--persistent'] else cm.ring)
    exit(0)
