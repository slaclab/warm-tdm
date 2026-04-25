from .client import Client
from .data import StreamData
from .utils import get_row_col

import os
import math
import re
import numpy as np
import matplotlib.pylab as plt
import matplotlib.colors as mcolors
from itertools import cycle
from scipy import signal, optimize


def add_channel_legend(ax):
    """
    Add a compact legend to ax, grouping entries by column (c#).

    Each column gets its own legend column, with rows listed top-to-bottom in
    ascending order. Font size is reduced iteratively until the legend fits
    within half the figure width and a third of the figure height.

    Args:
        ax (matplotlib.axes.Axes): Axes whose labeled artists will be included.

    Returns:
        matplotlib.legend.Legend: The created legend object.
    """
    handles, labels = ax.get_legend_handles_labels()

    # Group handles by column string (e.g. 'c0'), preserving all rows for each
    col_groups = {}
    for handle, label in zip(handles, labels):
        col = label[:label.index('r')]  # e.g. 'c0' from 'c0r5'
        if col not in col_groups:
            col_groups[col] = []
        col_groups[col].append((handle, label))

    # Sort columns and their rows numerically
    col_groups = {k: sorted(v, key=lambda x: int(x[1][x[1].index('r')+1:]))
                  for k, v in sorted(col_groups.items(), key=lambda x: int(x[0][1:]))}

    groups = list(col_groups.values())
    ncols = len(groups)
    nrows = max(len(g) for g in groups)

    # Pad shorter column groups with invisible entries so the grid is rectangular
    empty_handle = ax.plot([], [], alpha=0)[0]
    padded = [g + [(empty_handle, '')] * (nrows - len(g)) for g in groups]

    # Flatten column-by-column: matplotlib fills top-to-bottom, so this gives
    # the visual layout c0r0, c0r1, ... | c1r0, c1r1, ...
    ordered = [entry for col in padded for entry in col]
    ordered_handles, ordered_labels = zip(*ordered)

    legend = ax.legend(ordered_handles, ordered_labels, ncol=ncols)

    # Shrink font until legend fits within half-width, third-height of the figure
    fig = ax.get_figure()
    fig.canvas.draw()  # required to compute legend bounding box
    fig_w, fig_h = fig.get_size_inches() * fig.dpi
    max_w, max_h = fig_w / 2, fig_h / 3

    font_size = legend.get_texts()[0].get_fontsize()
    while font_size > 1:
        bbox = legend.get_window_extent()
        if bbox.width <= max_w and bbox.height <= max_h:
            break
        font_size -= 0.5
        for text in legend.get_texts():
            text.set_fontsize(font_size)
        fig.canvas.draw()

    return legend


def make_color_cycle(n, cmap='turbo'):
    """
    Return an infinite color iterator with n visually distinct colors from a colormap.

    Colors are sampled uniformly across the full colormap range, so even large n
    gets maximum spread.

    Args:
        n (int): Number of distinct colors needed.
        cmap (str): Matplotlib colormap name. Default is 'turbo'.

    Returns:
        itertools.cycle: Infinite iterator of RGBA tuples.
    """
    cm = plt.get_cmap(cmap)
    # Sample evenly: for n=1 this gives the midpoint; for n>1 it spans 0..1
    colors = [cm(i / max(n - 1, 1)) for i in range(n)]
    return cycle(colors)


def expand_channels(pattern_str, data, exclude=None):
    """
    Expand a comma-delimited string of channel patterns into a sorted list of channel strings.

    Patterns support:
      - Explicit:  c0r0
      - Wildcard:  c*r0, c0r*, c*r*
      - Range:     c0-3r0, c0r2-5, c0-3r2-5
      - Mixed:     c*r0-3, c0-3r*

    Channels with missing or empty data are warned about for explicit requests
    and silently skipped for wildcards and ranges.

    Args:
        pattern_str (str): Comma-delimited channel patterns, e.g. 'c*r0,c0-3r*'.
        data (dict): Nested data dict where data[col][row] holds sample lists.
        exclude (str, optional): Comma-delimited patterns to exclude, using the
            same syntax. Applied after all inclusions are resolved.

    Returns:
        list: Deduplicated, sorted list of channel strings, e.g. ['c0r0', 'c0r1', ...].
    """
    pattern = re.compile(r'^c(\*|\d+-\d+|\d+)r(\*|\d+-\d+|\d+)$')
    results = set()

    def expand_spec(spec, available):
        """Expand a single col or row spec ('*', 'N-M', or 'N') to a list of indices.

        Args:
            spec (str): The spec string.
            available (list): Indices present in data for bounds-checking.

        Returns:
            tuple: (indices, is_explicit) — is_explicit is True only for a single 'N'.
        """
        if spec == '*':
            return list(available), False
        elif '-' in spec:
            a, b = sorted(int(x) for x in spec.split('-'))
            return list(range(a, b + 1)), False
        else:
            return [int(spec)], True

    # Columns that have at least one non-empty row of data
    available_cols = [c for c in data.keys() if any(data[c][r] for r in data[c].keys())]

    for pat in [p.strip() for p in pattern_str.split(',')]:
        m = pattern.match(pat)
        if not m:
            print(f"Warning: '{pat}' is not a valid channel pattern, skipping.")
            continue

        col_spec, row_spec = m.group(1), m.group(2)
        cols, col_explicit = expand_spec(col_spec, available_cols)

        for col in cols:
            if col not in data or not any(data[col][r] for r in data[col].keys()):
                if col_explicit:
                    print(f"Warning: column {col} has no data, skipping.")
                continue

            available_rows = [r for r in data[col].keys() if data[col][r]]
            rows, row_explicit = expand_spec(row_spec, available_rows)
            is_explicit = col_explicit and row_explicit

            for row in rows:
                if row not in data[col] or not data[col][row]:
                    if is_explicit:
                        print(f"Warning: c{col}r{row} has no data, skipping.")
                    continue
                results.add(f'c{col}r{row}')

    # Apply exclusions by recursively expanding the exclude pattern string
    if exclude is not None:
        results -= set(expand_channels(exclude, data))

    return sorted(results, key=lambda s: (int(s[1:s.index('r')]), int(s[s.index('r')+1:])))


def plot_stream_data(crstring, exclude=None, stream_data_id=-1, yoffset=2, nperseg=10,
                     fs=396.332, sq1fb_to_pA=1224.23093499038):
    """
    Plot time-domain waveforms and frequency-domain ASDs for stream data channels.

    Produces a two-panel figure: left panel shows mean-subtracted waveforms offset
    vertically by yoffset; right panel shows Welch-estimated amplitude spectral
    densities (ASD) on a log-log scale.

    Args:
        crstring (str): Channel pattern string, e.g. 'c*r*' or 'c0r0-5,c1r*'.
            See expand_channels() for full syntax.
        exclude (str, optional): Channel patterns to exclude. Same syntax as crstring.
        stream_data_id (int): Index into StreamData._instances. Default is -1 (most recent).
        yoffset (float): Vertical separation between waveforms in the time plot (nA).
            Default is 2.
        nperseg (int): Welch method divides the time series into this many segments.
            Default is 10.
        fs (float): Sampling frequency in Hz. Default is 396.332.
        sq1fb_to_pA (float): Conversion factor from raw SQ1FB units to pA.
            Default is 1224.23093499038.

    Returns:
        dict: Results keyed by channel string. Each entry contains:
            't'    (ndarray): Time axis in seconds.
            'y'    (ndarray): Raw signal in pA.
            'y_ms' (ndarray): Mean-subtracted signal in pA.
            'freq' (ndarray): Frequency axis in Hz.
            'psd'  (ndarray): Power spectral density in pA²/Hz.
            'asd'  (ndarray): Amplitude spectral density in pA/√Hz.

    Raises:
        ValueError: If no channels match crstring after applying exclusions.
    """
    sd = StreamData._instances[stream_data_id]
    data = sd.data
    results = {}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 8))
    plt.suptitle(sd.file_name, fontsize=18)

    crs = expand_channels(crstring, data, exclude)
    if not crs:
        raise ValueError(f"No channels found matching '{crstring}' (exclude={exclude})")

    # --- Time domain ---
    color_cycle = make_color_cycle(len(crs))
    ylens = []
    for idx, cr in enumerate(crs):
        col, row = get_row_col(cr)
        results[cr] = {}
        results[cr]['y'] = np.array(data[col][row]) * sq1fb_to_pA
        results[cr]['t'] = (1. / fs) * np.array(range(len(results[cr]['y'])))
        ylens.append(len(results[cr]['y']))
        results[cr]['y_ms'] = results[cr]['y'] - np.mean(results[cr]['y'])
        # Offset each channel vertically so waveforms don't overlap
        ax1.plot(results[cr]['t'], (results[cr]['y_ms'] / 1.e3 - idx * yoffset),
                 alpha=1.0, color=next(color_cycle), label=f'{cr}')

    if len(np.unique(ylens)) != 1:
        print("Warning: some channels had different numbers of samples.")
    else:
        print(f"{np.unique(ylens)[0]} samples on all plotted channels.")

    ax1.set_xlabel('Time (sec)', fontsize=14)
    ax1.set_ylabel(r'TES Current Eq. (nA) [SQ1FB$\rightarrow$pA=' + f'{sq1fb_to_pA:.1f}]', fontsize=14)
    ax1.set_xlim(np.min(results[crs[0]]['t']), np.max(results[crs[0]]['t']))

    # --- Frequency domain ---
    color_cycle = make_color_cycle(len(crs))
    for cr in crs:
        # nperseg sets the number of Welch segments; more segments = smoother but lower resolution
        welch_nperseg = max(1, int(len(results[cr]['y_ms']) / nperseg))
        results[cr]['freq'], results[cr]['psd'] = signal.welch(
            results[cr]['y_ms'], nperseg=welch_nperseg, fs=fs)
        results[cr]['asd'] = np.sqrt(results[cr]['psd'])
        ax2.loglog(results[cr]['freq'], results[cr]['asd'],
                   alpha=0.8, label=f'{cr}', color=next(color_cycle))

    ax2.set_ylabel(r'TES Current Eq. ASD (pA$/\sqrt{Hz}$)', fontsize=16)
    ax2.set_xlabel('Frequency (Hz)', fontsize=14)
    # Lower x limit: ~2 full cycles fit in the time span; upper: Nyquist
    tspan = np.max(results[crs[0]]['t']) - np.min(results[crs[0]]['t'])
    ax2.set_xlim(2 / tspan, fs / 2)

    add_channel_legend(ax2)
    plt.tight_layout()

    return results


def analyze_pair(cr1, cr2, stream_data_id=-1, yoffset=2, nperseg=10, fs=396.332, sq1fb_to_pA=1224.23093499038,
                 do_fit=False, fit_freq_min=0.02, fit_freq_max=50, show_unfiltered=True, filter_f3db_hz=1,
                 p0=[125., 0.5, 0.1], bounds_low=[0., 0., 0.], bounds_high=[np.inf, np.inf, np.inf]):
    """
    Analyze and plot two stream data channels: time domain and ASD.

    Produces a two-panel figure. Left panel shows raw and low-pass filtered
    waveforms for cr1 and cr2, plus their difference divided by √2. Right panel
    shows the ASD for each channel, their difference ASD, and the mean ASD,
    with an optional noise model fit.

    Args:
        cr1 (str): First channel, e.g. 'c0r5'.
        cr2 (str): Second channel, e.g. 'c0r6'.
        stream_data_id (int): Index into StreamData._instances. Default -1 (most recent).
        yoffset (float): Vertical offset between waveforms in the time plot (nA). Default 2.
        nperseg (int): Number of Welch segments. Default 10.
        fs (float): Sampling frequency in Hz. Default 396.332.
        sq1fb_to_pA (float): SQ1FB-to-pA conversion factor. Default 1224.23093499038.
        do_fit (bool): Fit a 1/f + white noise model to the mean ASD. Default False.
        fit_freq_min (float): Lower frequency bound for the noise model fit in Hz. Default 0.02.
        fit_freq_max (float): Upper frequency bound for the noise model fit in Hz. Default 50.
        show_unfiltered (bool): Overlay unfiltered waveforms at half opacity. Default True.
        filter_f3db_hz (float): 3 dB cutoff of the low-pass filter in Hz. Default 1.
        p0 (list): Initial guess for noise model [white_level, n, f_knee]. Default [125, 0.5, 0.1].
        bounds_low (list): Lower bounds for noise model fit. Default [0, 0, 0].
        bounds_high (list): Upper bounds for noise model fit. Default [inf, inf, inf].

    Returns:
        dict: Results keyed by channel string. Each entry contains:
            't', 'y', 'y_ms', 'y_ms_filt', 'freq', 'psd', 'asd'.
            If do_fit=True, also includes fit parameters in the plot label.
    """
    sd = StreamData._instances[stream_data_id]
    data = sd.data

    # Design a 1st-order Butterworth low-pass filter for the time-domain display
    b, a = signal.butter(N=1, Wn=filter_f3db_hz, btype='low', fs=fs)
    zi = signal.lfilter_zi(b, a)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    plt.suptitle(sd.file_name, fontsize=18)
    # Use the default color cycle (only 2-3 traces so no need for make_color_cycle)
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    results = {}

    for idx, cr in enumerate([cr1, cr2]):
        col, row = get_row_col(cr)
        results[cr] = {}
        results[cr]['y'] = np.array(data[col][row]) * sq1fb_to_pA
        results[cr]['t'] = (1. / fs) * np.array(range(len(results[cr]['y'])))
        print(f"{cr} : len(y) = {len(results[cr]['y'])}")
        results[cr]['y_ms'] = results[cr]['y'] - np.mean(results[cr]['y'])
        # Apply low-pass filter with correct initial conditions to avoid edge transients
        results[cr]['y_ms_filt'] = signal.lfilter(b, a, results[cr]['y_ms'],
                                                   zi=zi * results[cr]['y_ms'][0])[0]
        if show_unfiltered:
            ax1.plot(results[cr]['t'], (results[cr]['y_ms'] / 1.e3 - idx * yoffset),
                     alpha=0.5, color=color_cycle[idx], label=f'{cr}')
        ax1.plot(results[cr]['t'], (results[cr]['y_ms_filt'] / 1.e3 - idx * yoffset),
                 alpha=1.0, color=color_cycle[idx], label=f'{cr}')

    # Difference channel: divided by sqrt(2) so uncorrelated noise reads as single-channel level
    if show_unfiltered:
        ax1.plot(results[cr1]['t'],
                 (results[cr2]['y_ms'] / 1.e3 - results[cr1]['y_ms'] / 1.e3) / np.sqrt(2) - (idx + 1) * yoffset,
                 alpha=0.5, color=color_cycle[idx + 1], label=f'{cr2}-{cr1}')
    ax1.plot(results[cr1]['t'],
             (results[cr2]['y_ms_filt'] / 1.e3 - results[cr1]['y_ms_filt'] / 1.e3) / np.sqrt(2) - (idx + 1) * yoffset,
             alpha=1.0, color=color_cycle[idx + 1], label=f'{cr2}-{cr1}')

    ax1.set_xlabel('Time (sec)', fontsize=14)
    ax1.set_ylabel(r'TES Current Eq. (nA) [SQ1FB$\rightarrow$pA=' + f'{sq1fb_to_pA:.1f}]', fontsize=14)

    # --- Frequency domain ---
    for idx, cr in enumerate([cr1, cr2]):
        welch_nperseg = max(1, int(len(results[cr]['y_ms']) / nperseg))
        results[cr]['freq'], results[cr]['psd'] = signal.welch(
            results[cr]['y_ms'], nperseg=welch_nperseg, fs=fs)
        results[cr]['asd'] = np.sqrt(results[cr]['psd'])
        ax2.loglog(results[cr]['freq'], results[cr]['asd'],
                   alpha=0.8, label=f'{cr}', color=color_cycle[idx])

    # Difference ASD: divide by sqrt(2) for same normalization as time domain
    y_ms_diff = results[cr2]['y_ms'] - results[cr1]['y_ms']
    welch_nperseg_diff = max(1, int(len(y_ms_diff) / nperseg))
    freq_diff, pxx_diff = signal.welch(y_ms_diff, nperseg=welch_nperseg_diff, fs=fs)
    asd_diff = np.sqrt(pxx_diff) / np.sqrt(2)
    ax2.loglog(freq_diff, asd_diff, alpha=0.5,
               label=f'({cr2}-{cr1})' + r'$/{\sqrt{2}}$', color=color_cycle[idx + 1])

    # Mean ASD across the two channels
    asd_mean = np.mean(np.stack([results[cr1]['asd'], results[cr2]['asd']], axis=0), axis=0)
    ax2.loglog(results[cr1]['freq'], asd_mean,
               c=color_cycle[idx + 2], label='mean asd', alpha=0.5)

    # Optional: fit a 1/f^n + white noise model to the mean ASD
    if do_fit:
        fridx = np.where((results[cr1]['freq'] > fit_freq_min) & (results[cr1]['freq'] < fit_freq_max))
        freq_fr = results[cr1]['freq'][fridx]
        asd_fit_fr = asd_mean[fridx]
        bounds = (bounds_low, bounds_high)
        popt, pcov = optimize.curve_fit(simple_noise_model, freq_fr, asd_fit_fr, p0=p0, bounds=bounds)
        wl, n, f_knee = popt
        ax2.loglog(results[cr1]['freq'], simple_noise_model(results[cr1]['freq'], *popt),
                   color=color_cycle[idx + 2], ls='--', lw=3,
                   label=(f'fit white-noise level = {wl:.2f}' +
                          r' pA/$\sqrt{Hz}$,' +
                          f' n = {n:.2f}' +
                          r', f$_{knee}$ = ' + f'{f_knee:.2f} Hz'))

    ax2.set_ylabel(r'TES Current Eq. ASD (pA$/\sqrt{Hz}$)', fontsize=16)
    ax2.set_xlabel('Frequency (Hz)', fontsize=14)
    ax2.set_xlim(np.min(results[cr1]['freq']), fs / 2)

    legend_font_size = 8 if do_fit else 12
    ax2.legend(loc='lower left', fontsize=legend_font_size)

    plt.tight_layout()
    return results


def simple_noise_model(freq, wl, n, f_knee):
    """
    1/f^n + white noise model for TES current noise ASD.

    Models the ASD as the sum of a white noise floor and a 1/f^n component
    that equals the white noise level at f_knee:

        ASD(f) = wl * (f_knee/f)^n + wl

    TODO: extend to include the DDS downsample filter transfer function.

    Args:
        freq (array-like): Frequency axis in Hz.
        wl (float): White noise level in pA/√Hz.
        n (float): Exponent of the 1/f component.
        f_knee (float): Knee frequency in Hz where 1/f == white noise level.

    Returns:
        ndarray: Model ASD in pA/√Hz.
    """
    A = wl * (f_knee ** n)  # amplitude of 1/f component
    return A / (freq ** n) + wl


def get_mean_raw_asd(col, idxpath, fsamp=125e6):
    """
    Compute the mean ASD across a set of raw waveform captures for one column.

    Reads file paths from an index file (one per line), loads each waveform,
    computes its periodogram, and averages the ASDs.

    Args:
        col (int): Column index to extract from each waveform file.
        idxpath (str): Path to the index file listing waveform .npy file paths.
        fsamp (float): ADC sampling rate in Hz. Default is 125e6 (125 MHz).

    Returns:
        tuple:
            freqs (ndarray): Frequency axis in Hz.
            mean_asd (ndarray): Mean ASD in V/√Hz.
            rms (float): RMS of the mean ASD (integral under the ASD curve).
    """
    datafiles = []
    asds = []

    # Read waveform file paths from the index file
    with open(idxpath, 'r') as file:
        for line in file:
            datafiles.append(line.strip())

    for datafile in datafiles:
        data = np.load(datafile, allow_pickle=True)
        vampin = data.item()[col]['V@AmpIn'][0]
        # Periodogram of mean-subtracted waveform gives the single-sided PSD
        freqs, Pxx_den = signal.periodogram(vampin - np.mean(vampin), fsamp, scaling='density')
        asds.append(np.sqrt(Pxx_den))

    mean_asd = np.mean(np.array(asds), axis=0)

    # RMS = sqrt of integral of PSD = sqrt(sum(ASD^2 * df))
    rms = np.sqrt(np.sum(mean_asd * mean_asd) * np.median(np.diff(freqs)))

    return freqs, mean_asd, rms


def plot_sq1curves(sq1tuneOutput, cols, rows):
    """
    Plot SQ1 tune curves (SA FB vs SQ1 FB) for each requested column/row.

    One figure per (col, row) pair. Each figure shows curves for all bias values,
    with the best-bias curve drawn thicker, peak/trough markers, and the selected
    tune point highlighted.

    Args:
        sq1tuneOutput (dict): Nested dict sq1tuneOutput[row][col] containing:
            'biasValues', 'bestIndex', 'peaks', 'phinots', 'xValues', 'curves',
            'highPoints', 'lowPoints', 'xOut', 'yOut'.
        cols (list): Column indices to plot.
        rows (list): Row indices to plot.
    """
    for col in cols:
        for row in rows:
            sq1crdict = sq1tuneOutput[row][col]

            plt.figure(tight_layout=True, figsize=(20, 10))
            plt.suptitle('SA FB (μA) vs. SQ1 FB (μA)')
            plt.title(f'Row {row} Column {col}')

            for bidx, bias in enumerate(sq1crdict['biasValues']):
                # Highlight the best bias with a thicker line
                linewidth = 2.0 if bidx == sq1crdict['bestIndex'] else 1.0
                peak = sq1crdict['peaks'][bidx]
                phinot = sq1crdict['phinots'][bidx]
                label = f'{bias:1.3f} - P-P: {peak:1.3f} - $\\phi_o$: {phinot:.2f}'
                color = plt.gca()._get_lines.get_next_color()

                plt.plot(sq1crdict['xValues'], sq1crdict['curves'][bidx],
                         label=label, linewidth=linewidth, color=color)
                # Mark peak (^) and trough (v)
                plt.plot(*sq1crdict['highPoints'][bidx], '^', color=color)
                plt.plot(*sq1crdict['lowPoints'][bidx], 'v', color=color)

            # Mark and annotate the selected tune point
            plt.plot(sq1crdict['xOut'], sq1crdict['yOut'], 's', label='Tune Point')
            plt.axhline(y=sq1crdict['yOut'], linestyle='--')
            plt.axvline(x=sq1crdict['xOut'], linestyle='--')

            plt.xlabel('SQ1 FB (μA)', fontsize=12)
            n = len(sq1crdict['biasValues'])
            plt.legend(ncol=math.ceil(n / 10), fontsize=8, loc='lower right')
            plt.grid(True)
            plt.tight_layout()
            plt.show()


#def plot_timing(waveform_filename, stack_on=None, align_on=None):
#    """Plot raw waveform data overplotted by row period, for timing verification."""
#    if not os.path.exists(waveform_filename):
#        print(f"Error: waveform file '{waveform_filename}' not found.")
#        return
#
#    waveform = np.load(waveform_filename, allow_pickle=True)
#
#    # Assumes ColumnBoard[0] is connected and in control
#    cb = Client.cbs[0]
#    RowPeriodCycles = cb.WarmTdmCore.Timing.TimingTx.RowPeriodCycles.value()
#    WaveformCaptureTime = cb.WarmTdmCore.Timing.TimingTx.WaveformCaptureTime.value()
#    NumRows = len(r.Group.RowIndexOrderList.get())
#
#    plt.figure()
#    vin_uV = waveform.item()[col]['V@AmpIn'][0] * 1.e6
#    ts_us = (np.arange(len(vin_uV)) + WaveformCaptureTime) * (1. / fadc) * 1e6
#    row_period_us = (1. / fadc) * 1e6 * RowPeriodCycles
#
#    # Overplot each array visit aligned to the start of its row period
#    for array_visit in range(int((np.max(ts_us) - np.min(ts_us)) / (row_period_us * NumRows))):
#        idxs = np.where(
#            (ts_us - (array_visit * row_period_us * NumRows) >= 0) &
#            ((ts_us - (array_visit * row_period_us * NumRows)) < row_period_us * NumRows)
#        )[0]
#        plt.plot(ts_us[idxs] - (array_visit * row_period_us * NumRows), vin_uV[idxs])
#
#    plt.xlim(0, row_period_us * NumRows)
#    plt.title(f'col{col}')
#    plt.xlabel('Time ($\mu$sec)')
#    plt.ylabel('V@AmpIn ($\mu$V)')
