#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
"""Rofi clipboard manager
Usage:
    roficlip.py --daemon [-q | --quiet]
    roficlip.py --show [--persistent | --actions] [-q | --quiet] [<index>]
    roficlip.py --add [-q | --quiet ]
    roficlip.py --remove [-q | --quiet]
    roficlip.py (-h | --help)
    roficlip.py (-v | --version)

Arguments:
    <index>         Index of item. Used by Rofi.

Commands:
    --daemon        Run clipboard manager daemon.
    --show          Show clipboard history.
    --persistent    Select to show persistent history.
    --actions       Select to show actions defined in config.
    --add           Add current clipboard to persistent storage.
    --remove        Remove current clipboard from persistent storage.
    -q, --quiet     Do not notify, even if notification enabled in config.
    -h, --help      Show this screen.
    -v, --version   Show version.

"""

import os
import stat
import errno
import struct
import gobject
import gtk
import yaml
import pynotify
from subprocess import PIPE, Popen
from xdg import BaseDirectory
from docopt import docopt


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
        self.cb = gtk.Clipboard()
        self.ring = self.read(self.ring_db)
        self.persist = self.read(self.persist_db)

        # Load settings
        self.load_config()

        # Init notifications
        if self.cfg['notify']:
            pynotify.init(name)

    def daemon(self):
        """
        Clipboard Manager daemon.
        """
        gobject.timeout_add(300, self.cb_watcher)
        gobject.timeout_add(300, self.fifo_watcher)
        gtk.main()

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
            self.cb.set_text(fifo_in)
            if self.cfg['notify']:
                self.notify_send('Copied to the clipboard.')
        return True

    def sync_items(self, clip, items):
        """
        Sync clipboard contents with specified dict when needed.
        Return "True" if dict modified, otherwise "False".
        """
        if clip and (not items or clip != items[0]):
            if clip in items:
                items.remove(clip)
            items.insert(0, clip)
            return True
        return False

    def copy_item(self, clip, items):
        """
        Writes to fifo item that should be copied to clipboard.
        """
        if clip:
            index = int(clip[0:clip.index(':')])
            with open(self.fifo_path, "w+") as file:
                file.write(items[index].encode('utf-8'))

    def show_items(self, items):
        """
        Format and show contents of specified dict (for rofi).
        """
        for index, clip in enumerate(items):
            clip = clip.replace('\n', self.cfg['newline_char']).encode('utf-8')
            preview = clip[0:self.cfg['preview_width']]
            print('{}: {}'.format(index, preview))

    def persistent_add(self):
        """
        Add current clipboard to persistent storage.
        """
        clip = self.cb.wait_for_text()
        if self.sync_items(clip, self.persist):
            self.write(self.persist_db, self.persist)
            if self.cfg['notify']:
                self.notify_send('Added to persistent.')

    def persistent_remove(self):
        """
        Remove current clipboard from persistent storage.
        """
        clip = self.cb.wait_for_text()
        if clip and clip in self.persist:
            self.persist.remove(clip)
            self.write(self.persist_db, self.persist)
            if self.cfg['notify']:
                self.notify_send('Removed from persistent.')

    def do_action(self, action):
        """
        Run selected action on clipboard contents.
        """
        if action:
            clip = self.cb.wait_for_text()
            key = action[action.index(':')+2:]
            params = self.actions[key].split(' ')
            while '%s' in params:
                params[params.index('%s')] = clip
            Popen(params, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            if self.cfg['notify']:
                self.notify_send(key)

    def notify_send(self, text):
        """
        Show desktop notification.
        """
        n = pynotify.Notification("Roficlip", text)
        n.set_timeout(self.cfg['notify_timeout'] * 1000)
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
                file.write("{0}{1}".format(struct.pack('>i', len(item)), item))

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
                'notify': True,
                'notify_timeout': 1,
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
    args = docopt(__doc__, version='0.4')
    if args['--quiet']:
        cm.cfg['notify'] = False
    if args['--daemon']:
        cm.daemon()
    elif (args['--show'] and not args['--actions']):
        if args['<index>']:
            cm.copy_item(args['<index>'],
                         cm.persist if args['--persistent'] else cm.ring)
        else:
            cm.show_items(cm.persist if args['--persistent'] else cm.ring)
    elif (args['--show'] and args['--actions']):
        if args['<index>']:
            cm.do_action(args['<index>'])
        else:
            cm.show_items(cm.actions)
    elif args['--add']:
        cm.persistent_add()
    elif args['--remove']:
        cm.persistent_remove()
    exit(0)
