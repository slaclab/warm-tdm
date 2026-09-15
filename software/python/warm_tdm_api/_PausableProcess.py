import threading

import pyrogue as pr


class PausableProcess(pr.Process):
    """A ``pr.Process`` with cooperative pause/resume checkpoints.

    Algorithms call :meth:`pausePoint` only between atomic hardware actions.
    ``Pause`` leaves the worker thread and its local state alive; invoking the
    existing ``Start`` command while paused releases the checkpoint.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Reuse Process._lock so Start, Stop, Pause, and pausePoint serialize
        # their state transitions through one condition.
        self._pauseCondition = threading.Condition(self._lock)
        self._pauseRequested = False
        self._resumeMessage = 'Running'

        self.add(pr.LocalCommand(
            name='Pause',
            function=self._pauseProcess,
            hidden=True,
            description='Pause at the next safe checkpoint. Start resumes.'))
        self.add(pr.LocalVariable(
            name='Paused',
            mode='RO',
            value=False,
            pollInterval=0.25,
            description='True after the worker reaches a pause checkpoint.'))

    def _startProcess(self):
        """Start an idle process or resume a paused running process."""
        with self._pauseCondition:
            worker_alive = (
                self._thread is not None
                and hasattr(self._thread, 'is_alive')
                and self._thread.is_alive())
            if self.Running.value() or worker_alive:
                if self._pauseRequested:
                    self._pauseRequested = False
                    self.Paused.set(False)
                    self.Message.set(self._resumeMessage)
                    self._pauseCondition.notify_all()
                else:
                    self._log.warning('Process already running!')
                return

        super()._startProcess()

    def _pauseProcess(self):
        """Request a pause without discarding the worker's local state."""
        with self._pauseCondition:
            worker_alive = (
                self._thread is not None
                and hasattr(self._thread, 'is_alive')
                and self._thread.is_alive())
            if not self.Running.value() and not worker_alive:
                self._log.warning('Cannot pause a process that is not running')
                return
            if self._pauseRequested:
                self._log.warning('Process pause already requested')
                return

            self._pauseRequested = True

    def _stopProcess(self):
        """Signal the worker to stop, waking and joining it if paused."""
        with self._pauseCondition:
            self._runEn = False
            self._pauseRequested = False
            self.Paused.set(False)
            thread = self._thread
            self._pauseCondition.notify_all()

        if (thread is not None
                and hasattr(thread, 'is_alive') and thread.is_alive()
                and hasattr(thread, 'join')
                and threading.current_thread() is not thread):
            thread.join()

    def _run(self):
        try:
            super()._run()
        finally:
            with self._pauseCondition:
                self._pauseRequested = False
                self.Paused.set(False)
                self._pauseCondition.notify_all()

    def _process(self):
        """Run a configured callback without labeling a stopped run Done."""
        if self._function is None:
            return super()._process()

        self.Message.set('Running')
        self.setStep(0)
        self.setProgress(0.0)

        arg = None if self._argVar is None else self._argVar.get()
        result = self._functionWrap(
            function=self._function, root=self.root, dev=self, arg=arg)

        if self._retVar is not None:
            self._retVar.set(result)

        if self._runEn:
            self.Message.set('Done')
            self.setProgress(1.0)
        elif not str(self.Message.value()).lower().startswith('stopped'):
            self.Message.set('Stopped')

    def pausePoint(self, publish=None):
        """Block at a requested pause and return whether processing may continue.

        ``publish`` is called immediately before acknowledging the pause. Tune
        processes use it to expose a stable serialized snapshot to plotters.
        """
        with self._pauseCondition:
            if self._pauseRequested and self._runEn:
                self._resumeMessage = self.Message.value()
                # Process callbacks run inside a long-lived updateGroup. Use a
                # short helper thread for the final snapshot/status updates so
                # its fresh tracker broadcasts them before this worker blocks.
                def acknowledge_pause():
                    try:
                        if publish is not None:
                            publish()
                    except Exception:
                        self._log.exception(
                            'Failed to publish the partial tuning result')
                    self.Paused.set(True)
                    self.Message.set('Paused; press Start to resume')

                publisher = threading.Thread(target=acknowledge_pause)
                publisher.start()
                publisher.join()
                self._pauseCondition.notify_all()

                while self._pauseRequested and self._runEn:
                    self._pauseCondition.wait()

            return self._runEn
