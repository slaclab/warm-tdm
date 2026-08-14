"""Group-level :class:`pyrogue.LinkVariable` subclasses.

These give a ``Group`` device single, ergonomic handles over dependencies that
are physically spread across the boards of a HardwareGroup, so callers set/get
one Group variable instead of walking the tree per board/channel:

* :class:`GroupBroadcastVariable` -- one scalar fanned out to many *identical*
  leaf nodes (e.g. cable resistance, an enable line).
* :class:`GroupLinkVariable` -- a 1-D array, one element per column, gated by a
  per-column ``tuneEnVar`` so disabled columns are skipped.
* :class:`GroupArrayLinkVariable` -- like ``GroupLinkVariable`` but each
  dependency is itself a per-board array of 8 channels; presents a flat
  ``numColumns``-long array (``col -> board*8 + chan``).
* :class:`FastDacVariable` -- a 2-D ``(column, row)`` array over the per-column
  fast-DAC drivers.

All of them run their get/set inside ``root.updateGroup()`` so the batched
dependency writes/reads coalesce into as few hardware transactions as possible.
The ``linkedSet``/``linkedGet`` callback parameter names (``value``, ``index``,
``write``, ``read``) are part of pyrogue's callback ABI -- pyrogue matches them
by name -- so keep them as-is.
"""

import pyrogue as pr
import numpy as np


class GroupBroadcastVariable(pr.LinkVariable):
    """One scalar value fanned out to many identical dependency Variables.

    The scalar sibling of :class:`GroupLinkVariable`: ``set(v)`` writes ``v`` to
    every dependency; ``get()`` returns the first dependency as a representative
    (all are kept in sync through this variable). No per-element array, no
    ``index``, no ``tuneEnVar`` -- use this when a single Group-level knob should
    drive a homogeneous set of leaf nodes across boards (e.g. cable resistance,
    an enable line).

    Parameters
    ----------
    dependencies : list[pr.BaseVariable]
        The leaf nodes to broadcast to. Must be homogeneous (accept the same
        set value); heterogeneous multi-field broadcasts want a custom
        ``LinkVariable`` instead.
    value_map : dict, optional
        Maps the logical value exposed here to the raw value each dependency
        expects, e.g. ``{False: 0, True: 1}`` for an enum RemoteVariable. The
        reverse map is applied on ``get``. Omit for a straight passthrough.
    empty_value : optional
        Value returned by ``get`` when there are no dependencies (default None).
    groups : sequence[str]
        Node groups. Defaults to ``('TopApi', 'NoConfig')``: the broadcaster is a
        convenience view, and the underlying leaf vars own config serialization,
        so it stays out of SaveConfig/LoadConfig to avoid a redundant (possibly
        stale) double-write on load.
    """

    def __init__(self, *, dependencies: list, value_map: dict | None = None,
                 empty_value=None, groups=('TopApi', 'NoConfig'), **kwargs):
        self._fwd = value_map
        self._rev = {raw: logical for logical, raw in value_map.items()} if value_map else None
        self._empty_value = empty_value
        super().__init__(
            dependencies=dependencies,
            groups=list(groups),
            linkedSet=self._set,
            linkedGet=self._get,
            **kwargs)

    def _set(self, *, value, write: bool) -> None:
        """Write ``value`` (mapped through ``value_map``) to every dependency."""
        raw = self._fwd[value] if self._fwd is not None else value
        for dep in self.dependencies:
            dep.set(value=raw, write=write)

    def _get(self, *, read: bool):
        """Return the first dependency's value as the representative for the set."""
        if len(self.dependencies) == 0:
            return self._empty_value
        raw = self.dependencies[0].get(read=read)
        return self._rev[raw] if self._rev is not None else raw


class GroupLinkVariable(pr.LinkVariable):
    """A 1-D per-column array over one scalar dependency per column.

    ``get(index=-1)`` returns all columns as a float64 array; ``get(index=n)``
    returns column ``n``. ``set`` mirrors that. Writes/reads are gated by
    ``tuneEnVar`` (a per-column bool array, typically ``Group.ColTuneEnable``):
    tune-disabled columns are skipped, so tuning a subset of columns does not
    disturb the rest. Units are inherited from the first dependency.

    Parameters
    ----------
    tuneEnVar : pr.BaseVariable, optional
        Per-column enable mask; ``None`` writes/reads every column.
    groups : str or sequence[str]
        Node groups (default ``'TopApi'``).
    disp : str
        Display format for each element.
    **kwargs
        Forwarded to :class:`pyrogue.LinkVariable`; must include
        ``dependencies`` (one scalar Variable per column).
    """

    def __init__(self, tuneEnVar=None, groups='TopApi', disp: str = '{:0.4f}', **kwargs):
        super().__init__(
            linkedSet=self._set,
            linkedGet=self._get,
            disp=disp,
            groups=groups,
            **kwargs)
        self.tuneEnVar = tuneEnVar
        deps = kwargs['dependencies']
        if len(deps) > 0:
            self._units = deps[0].units

    def _set(self, *, value, index: int, write: bool):
        """Write one column (``index >= 0``) or the whole array (``index == -1``),
        skipping tune-disabled columns."""
        if len(self.dependencies) == 0:
            return

        with self.parent.root.updateGroup():
            if index != -1:
                if self.tuneEnVar.get(index=index):
                    self.dependencies[index].set(value=value, write=write)
            else:
                for idx, (var, val) in enumerate(zip(self.dependencies, value)):
                    if self.tuneEnVar is not None and self.tuneEnVar.get(index=idx):
                        var.set(value=val, write=False)

                pr.writeAndVerifyBlocks(self.depBlocks)

    def _get(self, *, index: int, read: bool):
        """Read one column (``index >= 0``) or the whole array (``index == -1``)."""
        if len(self.dependencies) == 0:
            return 0
        with self.parent.root.updateGroup():
            if index != -1:
                ret = self.dependencies[index].get(read=read)
            else:
                ret = np.zeros(len(self.dependencies), np.float64)

                if read is True:
                    for idx, var in enumerate(self.dependencies):
                        if self.tuneEnVar.get(index=idx):
                            var.get(read=True, check=False)

                    for b in self.depBlocks:
                        pr.checkTransaction(b)

                for idx, var in enumerate(self.dependencies):
                    ret[idx] = var.get(read=False)

            return ret


class GroupArrayLinkVariable(GroupLinkVariable):
    """A flat ``numColumns``-long array whose dependencies are per-board arrays.

    Same 1-D column interface as :class:`GroupLinkVariable`, but each dependency
    is a per-board Variable holding 8 channels, so a global column index maps as
    ``board = col // 8``, ``chan = col % 8``. Used where the hardware exposes one
    array node per column board rather than one scalar per column.

    Parameters
    ----------
    config : GroupConfig
        Supplies ``numColumns`` (the flat array length).
    **kwargs
        Forwarded to :class:`GroupLinkVariable` (``tuneEnVar``, ``dependencies``,
        one per board, ...).
    """

    def __init__(self, config, **kwargs):
        self._config = config
        super().__init__(**kwargs)

    def _get(self, *, index: int = -1, read: bool = True):
        """Read one column (``index >= 0``) or all ``numColumns`` (``index == -1``)."""
        with self.parent.root.updateGroup():
            if index != -1:
                board = index // 8
                chan = index % 8
                ret = self.dependencies[board].get(index=chan, read=read)
            else:
                for dep in self.dependencies:
                    dep.get(read=read, check=False)

                for dep in self.dependencies:
                    dep.parent.checkBlocks()

                ret = np.zeros(self._config.numColumns, np.float64)
                for i in range(self._config.numColumns):
                    board = i // 8
                    chan = i % 8
                    ret[i] = self.dependencies[board].get(index=chan, read=False)

            return ret

    def _set(self, *, value, index: int, write: bool):
        """Write one column (``index >= 0``) or all ``numColumns`` (``index == -1``),
        skipping tune-disabled columns."""
        with self.parent.root.updateGroup():
            if index != -1:
                if self.tuneEnVar is not None and self.tuneEnVar.get(index=index):
                    board = index // 8
                    chan = index % 8
                    self.dependencies[board].set(value=value, index=chan, write=False)
            else:
                for idx in range(self._config.numColumns):
                    if self.tuneEnVar is not None and self.tuneEnVar.get(index=idx):
                        board = idx // 8
                        chan = idx % 8
                        self.dependencies[board].set(value=value[idx], index=chan, write=False)

            pr.writeAndVerifyBlocks(self.depBlocks)


class FastDacVariable(GroupLinkVariable):
    """A 2-D ``(column, row)`` array over the per-column fast-DAC drivers.

    Each dependency is a per-column fast-DAC node indexed by row. ``index`` is a
    ``(colIndex, rowIndex)`` pair for a single element, or ``-1`` for the whole
    2-D array (``numColumns`` rows of per-column row arrays). Defaults to
    ``hidden=True`` since these are large per-row tables driven by the tuning
    algorithms rather than set by hand.

    Parameters
    ----------
    config : GroupConfig
        Supplies ``numColumns``.
    **kwargs
        Forwarded to :class:`GroupLinkVariable` (``dependencies`` = one per-column
        fast-DAC node, ...).
    """

    def __init__(self, config, **kwargs):
        self._config = config

        if 'hidden' not in kwargs:
            kwargs['hidden'] = True

        super().__init__(disp='{:0.04f}', **kwargs)

    def _set(self, value, index, write: bool):
        """Write one ``(col, row)`` element (``index`` is a pair) or the whole
        2-D array (``index == -1``)."""
        with self.parent.root.updateGroup():
            if index != -1:
                colIndex = index[0]
                rowIndex = index[1]
                self.dependencies[colIndex].set(value=value, index=rowIndex, write=write)
            else:
                for colIndex in range(self._config.numColumns):
                    self.dependencies[colIndex].set(value=value[colIndex], index=-1, write=write)

    def _get(self, index, read: bool):
        """Read one ``(col, row)`` element (``index`` is a pair) or the whole
        2-D array (``index == -1``)."""
        with self.parent.root.updateGroup():
            if index != -1:
                colIndex = index[0]
                rowIndex = index[1]
                return self.dependencies[colIndex].get(index=rowIndex, read=read)
            else:
                cols = self._config.numColumns
                ret = [self.dependencies[colIndex].get(index=-1, read=read) for colIndex in range(cols)]
                return np.array(ret, dtype=np.float64)
