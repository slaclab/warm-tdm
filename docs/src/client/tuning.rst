Applying tuning results on the AwaXe maintenance branch
======================================================

Compatibility
-------------

``awaxe-software-fll`` starts at ``08de0a6`` (November 12,
2025), two TES-DAC corrections after the deployed software ``a4f7905``.
It retains that software's register interfaces, dependencies, data formats,
and legacy PID clearing. It is intended for column firmware ``ac5a0c4``
and row firmware ``b09c319``; no firmware rebuild is required for these
software changes. Physical FLL behavior still requires bench verification.

Use the site's existing working Python/Rogue environment for this upgrade.
The legacy ``conda.yml`` is not version-pinned; recreating it today does not
reproduce that environment. In particular, a local check with Rogue
``6.10.1.dev5`` constructed both processes but rejected their pre-existing
dictionary-to-list result publication under its newer type checks. This
branch does not backport the later Rogue compatibility changes.

The tuning corrections are adapted from ``1e0ba92`` (SA bias variable),
``075b702`` (SA force feedback before offset adjustment), and ``ec3039b``
(optional SQ1 operating-point application). The newer timing protocol,
row driver, hardware PID-clear command, and channelization formats are
not part of this branch.

Process controls
----------------

With timing stopped and hardware PID disabled, enable application before
starting each tuning process:

.. code-block:: python

   group.SaTuneProcess.SetAfterFinish.set(True)
   group.Sq1TuneProcess.ServoDisable.set(False)
   group.Sq1TuneProcess.SetAfterFinish.set(True)

Run SA tuning and wait for successful completion before proceeding to SQ1
tuning. Wait for SQ1 tuning to complete successfully and inspect its results
and table readbacks before starting multiplexed readout or enabling PID.
Both ``SetAfterFinish`` flags default to ``False``, preserving existing
workflows that apply results manually. Configure the flags on the server
after restarting it with this checkout, or through its connected client.

SA application sets ``SaBiasCurrent`` and copies the fitted feedback to
``SaFbCurrent`` for every configured row. It also loads that feedback into
``SaFbForceCurrent`` before running the final offset adjustment, so the
offset is measured at the fitted operating point while timing is stopped.

SQ1 application writes all three values for each enabled column and tuned row:

====================== ==================
Readout table          Fitted result field
====================== ==================
``Sq1BiasCurrent``     ``biasOut``
``Sq1FbCurrent``       ``xOut``
``SaFbCurrent``        ``yOut``
====================== ==================

``Sq1TuneOutput`` is in ``RowIndexOrderList`` order. Result position zero
therefore belongs to the first row in that list, which need not be row zero.
Application uses individual ``(column, row)`` writes, preserving disabled
columns and untuned rows without the legacy whole-table getter's 32-row
assumption. It does not adjust the offset again after fitting SQ1 curves.

Tunes stopped during acquisition do not apply their partial fits. Missing
or nonfinite fitted values in enabled columns raise an error before any
fitted values are written. Once application starts, it is not a hardware
transaction: a communication failure can still leave a partial update.
Check the process status and readbacks before enabling PID.

The sweeps still change force currents and offsets. Turning application off
does not restore the pre-tune analog state. ``ServoDisable=True`` is a
voltage diagnostic; its output cannot be applied as SA feedback current,
so it requires SQ1 ``SetAfterFinish=False``.

For direct Python calls, ``saTune(..., doSet=True)`` retains its existing
default. ``sq1Tune(group, process, doSet=True)`` opts into the new application;
omitting ``doSet`` retains the old measurement-only behavior.

Software checks
---------------

Run the focused regressions from the repository root:

.. code-block:: console

   python -m unittest discover -s software/tests -v

These checks require NumPy and replace acquisition and offset adjustment
with test doubles. They verify the operating-point handoff, row ordering,
disabled columns, cancellation, and invalid fits. They do not establish
hardware lock, ADC calibration, or compatibility with a particular Rogue
installation. The existing firmware's PID and timing limitations remain.
