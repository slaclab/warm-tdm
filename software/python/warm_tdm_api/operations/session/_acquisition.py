# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.

## Data acquisition: raw single-column captures, multi-capture, and timed runs
## through the DataWriter. Relies on TopologyCore state (self.hwg, self.cbs,
## self.root, self.coordinator_cb, self.col_to_board_chan, self._require_output).
## Mounted on Session.

import logging
import math
import os
import time


log = logging.getLogger(__name__)


class AcquisitionMixin:
    """Raw waveform captures and DataWriter-backed timed acquisition."""

    def take_raw(self, col, outputdir=None, synch=False, decimation=0,
                 check_delay_sec=0.1, timeout_sec=30.0):
        """Capture a raw waveform for a single column; return the saved path.

        Args:
            col (int): global column index.
            outputdir (str, optional): where to save; defaults to the session dir.
            synch (bool): synchronized vs asynchronous capture trigger.
            decimation (int): decimation factor (0 = none).
            check_delay_sec (float): poll interval while waiting for the file.
            timeout_sec (float): max wait before raising TimeoutError.

        Raises:
            TimeoutError: if no new waveform file appears within timeout_sec.
        """
        wcr = self.hwg.WaveformCaptureReceiver
        last_raw0 = wcr.LastSavedFileName.get()

        board, chan = self.col_to_board_chan(col)
        cb = self.cbs[board]

        if outputdir is None:
            outputdir = self._require_output()

        wcr.SavedFilePath.set(outputdir)
        wcr.SaveData.set(True)

        cb.DataPath.WaveformCapture.AllChannels.set(False)
        cb.DataPath.WaveformCapture.SelectedChannel.set(chan)
        cb.DataPath.WaveformCapture.Decimation.set(decimation)
        wcr.PlotColumn.set(chan)
        wcr.PlotWaveform.set(True)

        if synch:
            cb.WarmTdmCore.Timing.TimingTx.WaveformCapture()
        else:
            cb.DataPath.WaveformCapture.CaptureWaveform()

        # Wait for the waveform to be saved to disk (bounded by timeout_sec).
        last_raw = None
        deadline = time.time() + timeout_sec
        try:
            while True:
                if last_raw is not None:
                    if last_raw != last_raw0 and os.path.getsize(last_raw) > 0:
                        break
                if time.time() > deadline:
                    raise TimeoutError(
                        f"take_raw: no new waveform file for column {col} within "
                        f"{timeout_sec} s (last seen: {last_raw!r}).")
                time.sleep(check_delay_sec)
                last_raw = wcr.LastSavedFileName.get()
        finally:
            # Always disable waveform capture, even if we timed out.
            wcr.SaveData.set(False)

        return last_raw

    def multi_raw(self, col, nraw, synch=False, decimation=0):
        """Capture nraw waveforms for one column into a raw_<ctime>/ dir.

        Returns the path to a text index file listing the saved waveform paths.
        """
        ctime = int(time.time())
        save_dir = os.path.join(self._require_output(), f'raw_{ctime}')
        os.makedirs(save_dir, exist_ok=True)

        # Enable msec timestamping for high-cadence acquisition, then restore.
        ms_ts = self.hwg.WaveformCaptureReceiver.MillisecondTimestamp
        previous_ms_ts = ms_ts.get()
        ms_ts.set(True)

        wfs = []
        try:
            for _ in range(nraw):
                wfs.append(self.take_raw(col=col, outputdir=save_dir, synch=synch,
                                         decimation=decimation))
        finally:
            ms_ts.set(previous_ms_ts)

        idxfp = os.path.join(save_dir, f'raw_{ctime}.txt')
        with open(idxfp, 'w') as f:
            for wf in wfs:
                f.write(f"{wf}\n")

        print(f"{nraw} waveforms indexed to {idxfp} for column {col}.")
        return idxfp

    def take_data(self, acq_time_sec, start_delay_sec=1.0):
        """Open the DataWriter, acquire for acq_time_sec, then close.

        Starts the run if not already running (and stops it again afterward,
        leaving a pre-existing run running). Cleanup attempts both writer close
        and EndRun even on startup, file or interrupt errors. Cleanup failures
        are reported; an already-open writer is never taken over.
        """
        cb0 = self.coordinator_cb
        tx = cb0.WarmTdmCore.Timing.TimingTx

        for name, value in [('acq_time_sec', acq_time_sec),
                            ('start_delay_sec', start_delay_sec)]:
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")

        writer = self.root.DataWriter
        if writer.IsOpen.get():
            raise RuntimeError("DataWriter is already open; refusing to replace its file")
        was_running = tx.Running.get()
        start_attempted = False
        open_attempted = False
        failed = False
        try:
            if not was_running:
                # A command may take effect before reporting a transport error.
                start_attempted = True
                tx.StartRun()
                time.sleep(start_delay_sec)

            writer.AutoName()
            writer.DataFile.set(os.path.join(
                os.path.abspath(self._require_output()), writer.DataFile.get()))
            data_filename = writer.DataFile.get()
            print(f'Open file {data_filename}')
            open_attempted = True
            writer.Open()
            print(f'Acquire data for {acq_time_sec} sec ...')
            time.sleep(acq_time_sec)
        except BaseException:
            failed = True
            raise
        finally:
            # Both cleanup actions must run, even when one fails. Preserve the
            # original acquisition/interrupt error and log cleanup failures.
            cleanup_errors = []
            if open_attempted:
                try:
                    writer.Close()
                except BaseException as exc:
                    cleanup_errors.append(exc)
                    log.exception("take_data: failed to close DataWriter")
            if start_attempted:
                try:
                    tx.EndRun()
                except BaseException as exc:
                    cleanup_errors.append(exc)
                    log.exception("take_data: failed to stop the run it started")
            if cleanup_errors and not failed:
                raise cleanup_errors[0]

        return data_filename
