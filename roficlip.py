#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

import os
import stat
import errno
import struct
import gobject
import gtk
from sys import argv
from xdg import BaseDirectory


# Settings
RING_LIMIT = 20
STRING_LIMIT = 200
DAEMON_DELAY = 500
HELP = '''./mclip.py show|daemon'''


class ClipboardManager():
    def __init__(self):
        # Init databases and fifo
        name = 'mclip'
        self.ring_db = '{0}/{1}'.format(BaseDirectory.save_data_path(name), 'ring.db')
        self.fifo_path = '{0}/{1}.fifo'.format(BaseDirectory.get_runtime_dir(strict=False), name)
        if not os.path.isfile(self.ring_db):
            open(self.ring_db, "a+").close()
        if (
            not os.path.exists(self.fifo_path) or
            not stat.S_ISFIFO(os.stat(self.fifo_path).st_mode)
        ):
            os.mkfifo(self.fifo_path)
        self.fifo = os.open(self.fifo_path, os.O_RDONLY | os.O_NONBLOCK)
        # Init clipboard
        self.cb = gtk.Clipboard()
        self.ring = self.read(self.ring_db)

    def daemon(self):
        """
        Clipboard Manager daemon.
        """
        gobject.timeout_add(DAEMON_DELAY, self.ring_input)
        gobject.timeout_add(DAEMON_DELAY, self.ring_output)
        gtk.main()

    def ring_input(self):
        """
        Callback function.
        Watch clipboard and write changes to ring database.
        Must return "True" for continuous operation.
        """
        clip = self.cb.wait_for_text()
        if clip and (not self.ring or clip != self.ring[0]):
            if clip in self.ring:
                self.ring.remove(clip)
            self.ring.insert(0, clip)
            self.write(self.ring_db, self.ring[0:RING_LIMIT])
        return True

    def ring_output(self):
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
        return True

    def ring_show(self):
        """
        Format and show ring contents (for rofi).
        """
        for index, clip in enumerate(self.ring):
            clip = clip.replace('\n', '¬').encode('utf-8')
            print('{}: {}'.format(index, clip[0:STRING_LIMIT]))

    def clip_copy(self, clip):
        """
        Writes to fifo clip that should be copied to clipboard.
        """
        if clip:
            index = int(clip[0:clip.index(':')])
            with open(self.fifo_path, "w+") as file:
                file.write(self.ring[index].encode('utf-8'))

    def read(self, fd):
        """
        Helper function. Data reader.
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
        Helper function. Data writer.
        """
        with open(fd, 'wb') as file:
            for item in items:
                item = item.encode('utf-8')
                file.write("{0}{1}".format(struct.pack('>i', len(item)), item))


if __name__ == "__main__":
    cm = ClipboardManager()

    if len(argv) <= 1:
        print(HELP)
    elif argv[1] == 'daemon':
        cm.daemon()
    elif argv[1] == 'show' and len(argv) == 2:
        cm.ring_show()
    elif argv[1] == 'show' and len(argv) > 2:
        cm.clip_copy(argv[2])
    else:
        print(HELP)
    exit(0)
