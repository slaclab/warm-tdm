##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Selection limits, topology validation and detachable sample listeners."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
from unittest.mock import Mock, patch

import numpy as np
import pytest

WIDGETS = Path(__file__).resolve().parents[1] / 'python/warm_tdm_api/widgets'


def load(name):
    spec = importlib.util.spec_from_file_location(name, WIDGETS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


selection = load('_pid_selection')


def test_ranges_deduplicate_and_form_cartesian_product():
    topology = {c: set(range(16)) for c in (0, 3, 8)}
    result = selection.channel_pairs('0, 3, 8, 3', '10-15, 12', topology)
    assert len(result) == 18
    assert result[0] == (0, 10) and result[-1] == (8, 15)


@pytest.mark.parametrize('text', ['', '1,,2', '-1', '3-1', 'a', '1.0', '0-999999999999999999'])
def test_invalid_ranges_do_not_expand_unbounded_input(text):
    with pytest.raises(ValueError):
        selection.parse_indices(text, range(16))


def test_sparse_topology_and_total_limit():
    with pytest.raises(ValueError, match='unavailable'):
        selection.channel_pairs('0-2', '0', {0: {0}, 2: {0}})
    with pytest.raises(ValueError, match='Some rows'):
        selection.channel_pairs('0, 2', '0-1', {0: {0, 1}, 2: {0}})
    with pytest.raises(ValueError, match='at most'):
        selection.channel_pairs('0-7', '0-15', {c: set(range(16)) for c in range(8)})


class Node:
    def __init__(self, value=False):
        self.listeners = []
        self.current = value
        self.set = Mock(side_effect=self._set)

    def _set(self, value):
        self.current = value

    def get(self, read=False):
        assert read is False
        return self.current

    def addListener(self, callback):
        self.listeners.append(callback)

    def delListener(self, callback):
        self.listeners.remove(callback)

    def publish(self, value):
        for callback in list(self.listeners):
            callback('path', SimpleNamespace(value=value))


def test_subscriptions_detach_without_stopping_shared_client_and_reject_old_callbacks():
    sample0, sample1, enable = Node(), Node(), Node()
    hardware = SimpleNamespace(
        PidDebug={0: SimpleNamespace(RowPids=SimpleNamespace(PID={
            0: SimpleNamespace(Sample=sample0), 1: SimpleNamespace(Sample=sample1)}))},
        ColumnBoard={0: SimpleNamespace(DataPath=SimpleNamespace(AdcDsp={
            0: SimpleNamespace(PidDebugEnable=enable)}))})
    client = SimpleNamespace(root=SimpleNamespace(getNode=lambda path: SimpleNamespace(HardwareGroup=hardware)),
        linked=True, addLinkMonitor=Mock(), remLinkMonitor=Mock(), stop=Mock())
    interface = ModuleType('pyrogue.interfaces')
    interface.VirtualClient = lambda host, port: client
    plugin = ModuleType('pyrogue.pydm.data_plugins.rogue_plugin')
    plugin.parseAddress = lambda address: ('localhost', 9099, 'GroupRoot.Group', 'value', -1)
    with patch.dict(sys.modules, {'pyrogue.interfaces': interface,
                                 'pyrogue.pydm.data_plugins.rogue_plugin': plugin}):
        source_module = load('_pid_source')
    source = source_module.PidSampleSource('address')
    source.select([(0, 0), (0, 1)])
    assert len(enable.listeners) == 1  # One enable listener for two rows.
    sample = np.arange(11, dtype=float)
    sample0.publish(sample)
    sample[:] = 99
    assert source.drain()[2]['sample', 0, 0][0][0] == 0  # Owned snapshot.
    old = sample0.listeners[0]
    source.select([(0, 1)])
    assert not sample0.listeners
    source.select([(0, 0), (0, 1)])
    old('path', SimpleNamespace(value=np.zeros(11)))
    assert not source.drain()[2]  # A removed subscription cannot fill a new history.
    for i in range(100):
        sample1.publish(np.full(11, i))
    assert len(source.drain()[2]['sample', 0, 1]) == 64
    sample1.publish(np.ones(11))
    source._link_changed(False)
    sample1.publish(np.ones(11))
    linked, epoch, pending = source.drain()
    assert not linked and epoch == 1 and not pending
    source._link_changed(True)
    source.set_debug(0, True)
    assert source.debug_enabled(0)
    enable.set.assert_called_once_with(True)
    source.close()
    source.close()  # QWidget destruction after close is harmless.
    assert not sample0.listeners and not sample1.listeners and not enable.listeners
    client.stop.assert_not_called()
