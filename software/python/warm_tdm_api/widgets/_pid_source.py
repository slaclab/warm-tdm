##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Detachable listeners on existing Rogue samples; never own/stop the shared client."""
from collections import deque
from threading import Lock

import numpy as np
from pyrogue.interfaces import VirtualClient
from pyrogue.pydm.data_plugins.rogue_plugin import parseAddress


class PidSampleSource:
    def __init__(self, address):
        host, port, path, _, _ = parseAddress(address)
        self.client = VirtualClient(host, port)
        group = self.client.root.getNode(path)
        self.hardware = group.HardwareGroup
        self.debuggers = self.hardware.PidDebug
        self.topology = {c: set(debug.RowPids.PID) for c, debug in self.debuggers.items()}
        self._lock = Lock()
        self._listeners = {}
        self._pending = {}
        self._linked = self.client.linked
        self._epoch = 0
        self.client.addLinkMonitor(self._link_changed)

    def _link_changed(self, linked):
        with self._lock:
            self._linked = linked
            self._epoch += 1
            self._pending.clear()

    def _subscribe(self, key, node):
        if key in self._listeners:
            return
        token = object()

        def changed(path, value):
            # Rogue invokes this on its receive thread. Qt work happens only in drain().
            data = value.value
            if isinstance(data, np.ndarray):
                data = data.copy()
            with self._lock:
                current = self._listeners.get(key)
                if current is not None and current[2] is token and self._linked:
                    self._pending.setdefault(key, deque(maxlen=64)).append(data)

        with self._lock:
            self._listeners[key] = (node, changed, token)
        node.addListener(changed)

    def _unsubscribe(self, key):
        with self._lock:
            entry = self._listeners.pop(key, None)
            self._pending.pop(key, None)
        if entry is not None:
            entry[0].delListener(entry[1])

    def select(self, pairs):
        wanted = {('sample', c, r) for c, r in pairs}
        wanted.update(('enable', c) for c, _ in pairs)
        for key in set(self._listeners) - wanted:
            self._unsubscribe(key)
        for key in sorted(wanted - self._listeners.keys()):
            if key[0] == 'sample':
                _, c, r = key
                node = self.debuggers[c].RowPids.PID[r].Sample
            else:
                node = self.enable_node(key[1])
            self._subscribe(key, node)
        # Do not fetch cached samples: a new selection waits for a fresh visit.

    def enable_node(self, column):
        return self.hardware.ColumnBoard[column // 8].DataPath.AdcDsp[column % 8].PidDebugEnable

    def set_debug(self, column, enabled):
        self.enable_node(column).set(bool(enabled))

    def debug_enabled(self, column):
        return bool(self.enable_node(column).get(read=False))

    def drain(self):
        with self._lock:
            pending, self._pending = self._pending, {}
            return self._linked, self._epoch, pending

    def discard(self):
        with self._lock:
            self._pending.clear()

    def close(self):
        self.client.remLinkMonitor(self._link_changed)
        for key in list(self._listeners):
            self._unsubscribe(key)
