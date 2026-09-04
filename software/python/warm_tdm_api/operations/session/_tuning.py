## Tuning: start-and-block wrappers over the Group pr.Process nodes (SaOffset,
## SaTune, Sq1Tune, FasTune, ...). Relies on TopologyCore state (self.group).
## Mounted on Session.

import time


class TuningMixin:
    """Start-and-block wrappers over the Group tuning ``pr.Process`` nodes."""

    # Named tuning processes and their output variable, so the wrappers can
    # return the result the algorithm produced. Every warm_tdm_api tuning
    # algorithm is a pr.Process on Group with the uniform Start/Stop/Running/
    # Progress/Message interface; run_process drives any of them by node name.
    _PROCESS_OUTPUT = {
        'SaOffsetProcess': 'SaOffsetOutput',
        'SaTuneProcess': 'SaTuneOutput',
        'Sq1TuneProcess': 'Sq1TuneOutput',
        'FasTuneProcess': 'FasTuneOutput',
    }

    def run_process(self, name, block=True, poll_sec=1.0, timeout_sec=None,
                    **params):
        """Configure, start, and (optionally) block on a Group ``pr.Process``.

        Replaces the hand-rolled ``proc.Start(); while proc.Running.get(): ...``
        idiom (see the old ``scripts/Jupyter.py``). Any of the Group tuning
        processes -- SaOffset, SaTune, Sq1Tune, FasTune, ... -- is driven by node
        name, since they all share the ``pr.Process`` interface.

        Args:
            name (str): the Group child process node, e.g. ``'SaTuneProcess'``.
            block (bool): if True, poll ``Running`` until the process finishes
                (or ``timeout_sec`` elapses) before returning; if False, Start
                and return immediately.
            poll_sec (float): poll interval while blocking.
            timeout_sec (float | None): max wall time to block; None = no limit.
            **params: process variable settings applied before Start, e.g.
                ``SaBiasNumSteps=5``. Unknown names raise AttributeError.

        Returns:
            The process's output value if it exposes a known output variable and
            we blocked to completion; otherwise None. (When ``block=False`` the
            result is not ready yet -- poll/collect via the process node.)

        Raises:
            AttributeError: no such process node, or an unknown param name.
            TimeoutError: the process was still running at ``timeout_sec``.
        """
        try:
            proc = getattr(self.group, name)
        except AttributeError:
            raise AttributeError(
                f"No process '{name}' on Group. Known tuning processes: "
                f"{sorted(self._PROCESS_OUTPUT)}.")

        for k, v in params.items():
            getattr(proc, k).set(v)  # AttributeError here = bad param name

        proc.Start()
        if not block:
            return None

        deadline = None if timeout_sec is None else time.time() + timeout_sec
        try:
            while proc.Running.get():
                if deadline is not None and time.time() > deadline:
                    raise TimeoutError(
                        f"{name} still running after {timeout_sec} s "
                        f"(last message: {proc.Message.get()!r}).")
                time.sleep(poll_sec)
        except KeyboardInterrupt:
            # Interrupting the wait should stop the process, not orphan it.
            proc.Stop()
            raise

        msg = proc.Message.get()
        if msg:
            print(f"{name}: {msg}")

        out_var = self._PROCESS_OUTPUT.get(name)
        if out_var is not None:
            return getattr(proc, out_var).get()
        return None

    def sa_offset(self, block=True, **params):
        """Run SaOffsetProcess (SA offset determination). See run_process."""
        return self.run_process('SaOffsetProcess', block=block, **params)

    def sa_tune(self, block=True, **params):
        """Run SaTuneProcess (SA amplifier tuning). See run_process.

        Example: ``sess.sa_tune(SaBiasLowOffset=.4, SaBiasHighOffset=.8,
        SaBiasNumSteps=5)``.
        """
        return self.run_process('SaTuneProcess', block=block, **params)

    def sq1_tune(self, block=True, **params):
        """Run Sq1TuneProcess (first-stage SQUID tuning). See run_process."""
        return self.run_process('Sq1TuneProcess', block=block, **params)

    def fas_tune(self, block=True, **params):
        """Run physical-line FasTuneProcess. See run_process.

        ``Sq1BiasCurrent`` selects the temporary bootstrap SQ1 bias applied to
        enabled columns during acquisition (40 uA by default). The previous
        SQ1 bias and feedback force currents are restored afterward. Before
        each logical-row sweep, its SA-tuned ``SaFbCurrent`` values are copied
        into the ``SaFbForceCurrent`` path used while timing is stopped.
        ``FasFluxSampleReads`` and ``ServoSampleReads`` control how many ADC
        reads are discarded after row-FAS and SA-feedback writes so cosim time
        advances before the measurement is used. ``FasMinimumTolerance`` is
        the SA-feedback band above the sampled minimum whose contiguous region
        is centered to select the FAS-on candidate; disabled columns are not
        included in the acquired curves.
        Pass ``SetAfterFinish=True`` to program the fitted ``FasOn`` currents;
        the default only returns the candidates.
        """
        return self.run_process('FasTuneProcess', block=block, **params)
