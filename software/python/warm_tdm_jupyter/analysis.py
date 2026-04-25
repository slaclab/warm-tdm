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
    Add a legend to an axes where each distinct column (c#) gets its own legend column.
    Entries are grouped by column number, with each group in its own legend column.
    No column headers are shown. The legend is sized to be no more than 1/2 the width
    and 1/3 the height of the figure.

    Args:
        ax (matplotlib.axes.Axes): The axes containing the labeled artists.

    Returns:
        matplotlib.legend.Legend: The created legend.
    """
    handles, labels = ax.get_legend_handles_labels()

    # Group by column, sorted by ascending column then ascending row
    col_groups = {}
    for handle, label in zip(handles, labels):
        col = label[:label.index('r')]  # e.g. 'c0'
        if col not in col_groups:
            col_groups[col] = []
        col_groups[col].append((handle, label))

    # Sort columns and rows numerically
    col_groups = {k: sorted(v, key=lambda x: int(x[1][x[1].index('r')+1:])) 
                  for k, v in sorted(col_groups.items(), key=lambda x: int(x[0][1:]))}

    # Reorder handles/labels so each column's entries are contiguous
    groups = list(col_groups.values())
    ncols = len(groups)
    nrows = max(len(g) for g in groups)

    # Pad shorter groups with empty entries
    empty_handle = ax.plot([], [], alpha=0)[0]
    padded = [g + [(empty_handle, '')] * (nrows - len(g)) for g in groups]

    # Flatten column-by-column so matplotlib's top-to-bottom fill
    # produces c0r0,c0r1... c1r0,c1r1... visual ordering
    ordered = [entry for col in padded for entry in col]
    ordered_handles, ordered_labels = zip(*ordered)

    legend = ax.legend(ordered_handles, ordered_labels, ncol=ncols)

    # Iteratively reduce font size until legend fits within size constraints
    fig = ax.get_figure()
    fig.canvas.draw()  # needed to compute legend size

    fig_w, fig_h = fig.get_size_inches() * fig.dpi  # figure size in pixels
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
    Create an infinite color cycle with colors evenly distributed across a colormap.

    Colors are sampled uniformly across the full range of the colormap based on
    the total number of colors requested, ensuring maximum visual distinction
    between colors regardless of n.

    Args:
        n (int): Total number of distinct colors needed.
        cmap (str): Matplotlib colormap name. Default is 'jet'.

    Returns:
        itertools.cycle: An infinite iterator of RGBA color tuples.
    """
    cm = plt.get_cmap(cmap)
    colors = [cm(i / max(n - 1, 1)) for i in range(n)]
    return cycle(colors)

def expand_channels(pattern_str, data, exclude=None):
    """
    Expand a comma-delimited string of channel patterns into a list of channel strings.
    
    Patterns support:
      - Explicit:  c0r0
      - Wildcard:  c*r0, c0r*, c*r*
      - Range:     c0-3r0, c0r2-5, c0-3r2-5
      - Mixed:     c*r0-3, c0-3r*
    
    Channels with missing or empty data are warned for explicit requests, silently 
    skipped for wildcards and ranges.

    Args:
        pattern_str (str): Comma-delimited channel patterns e.g. 'c*r0,c0-3r*'
        data (dict): Nested data dictionary where data.keys() are column indices
                     and data[col].keys() are row indices.
        exclude (str, optional): Comma-delimited channel patterns to exclude,
                     using the same syntax as pattern_str. Excluded channels are
                     removed after all inclusions are resolved. Default is None.
    
    Returns:
        list: Deduplicated, sorted list of channel strings e.g. ['c0r0', 'c0r1', ...]
    """
    pattern = re.compile(r'^c(\*|\d+-\d+|\d+)r(\*|\d+-\d+|\d+)$')
    results = set()

    def expand_spec(spec, available):
        """Expand a single col or row spec into a list of indices.
        
        Args:
            spec (str): One of '*', 'N-M', or 'N'
            available (list): Available indices from data
        
        Returns:
            tuple: (indices, is_explicit) where is_explicit indicates single explicit value
        """
        if spec == '*':
            return list(available), False
        elif '-' in spec:
            a, b = sorted(int(x) for x in spec.split('-'))
            return list(range(a, b + 1)), False
        else:
            return [int(spec)], True

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

    if exclude is not None:
        results -= set(expand_channels(exclude, data))

    return sorted(results, key=lambda s: (int(s[1:s.index('r')]), int(s[s.index('r')+1:])))

def plot_stream_data(crstring, exclude=None, stream_data_id=-1, yoffset=2, nperseg=10, 
                     fs=396.332, sq1fb_to_pA=1224.23093499038):
    """
    Plot the time and frequency domain characteristics of stream data channels.
    """
    # If no index given, load most recent dataset
    sd = StreamData._instances[stream_data_id]
    data = sd.data

    # Dictionary to return with results
    results = {}

    # Time domain plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 8))
    plt.suptitle(sd.file_name, fontsize=18)

    crs=expand_channels(crstring,data,exclude)
    if not crs:
        raise ValueError(f"No channels found matching '{crstring}' (exclude={exclude})")
    
    color_cycle = make_color_cycle(len(crs))
    ylens=[] # check that same number of samples in every channel
    for idx, cr in enumerate(crs):
        (col, row) = get_row_col(cr)
        results[cr] = {}
        results[cr]['y'] = np.array(data[col][row]) * sq1fb_to_pA
        results[cr]['t'] = (1. / fs) * (np.array(range(len(results[cr]['y']))))
        #print(f"{cr} : len(y) = {len(results[cr]['y'])}")
        ylens.append(len(results[cr]['y']))
        results[cr]['y_ms'] = results[cr]['y'] - np.mean(results[cr]['y'])
        ax1.plot(results[cr]['t'], (results[cr]['y_ms'] / 1.e3 - idx * yoffset), alpha=1.0, color=next(color_cycle), label=f'{cr}')
    if len(np.unique(ylens))!=1:
        print(f"Warning: some channels had different numbers of samples.")
    else:
        print(f"{np.unique(ylens)[0]} samples on all plotted channels.")

    ax1.set_xlabel('Time (sec)', fontsize=14)
    ylabel_ax1 = r'TES Current Eq. (pA) [SQ1FB$\rightarrow$pA=' + f'{sq1fb_to_pA:.1f}]'
    ax1.set_ylabel(ylabel_ax1, fontsize=14)
    ax1.set_xlim(np.min(results[cr]['t']),np.max(results[cr]['t']))

    # Frequency domain analysis
    color_cycle = make_color_cycle(len(crs))
    for idx, cr in enumerate(crs):
        welch_nperseg = max(1, int(len(results[cr]['y_ms']) / nperseg))
        results[cr]['freq'], results[cr]['psd'] = signal.welch(results[cr]['y_ms'], nperseg=welch_nperseg, fs=fs)
        results[cr]['asd'] = np.sqrt(results[cr]['psd'])
        ax2.loglog(results[cr]['freq'], results[cr]['asd'], alpha=0.8, label=f'{cr}', color=next(color_cycle))
    
    ax2.set_ylabel(r'TES Current Eq. ASD (pA$/\sqrt{Hz}$)',fontsize=16)
    ax2.set_xlabel('Frequency (Hz)', fontsize=14)
    tspan=np.max(results[cr]['t'])-np.min(results[cr]['t'])
    ax2.set_xlim(2 / tspan, fs / 2)

    add_channel_legend(ax2)

    plt.tight_layout()

    return results

def analyze_pair(cr1, cr2, stream_data_id=-1, yoffset=2, nperseg=10, fs=396.332, sq1fb_to_pA=1224.23093499038,
                 do_fit=False, fit_freq_min=0.02, fit_freq_max=50, show_unfiltered=True, filter_f3db_hz=1,
                 p0=[125., 0.5, 0.1], bounds_low=[0., 0., 0.], bounds_high=[np.inf, np.inf, np.inf]):
    """
    Analyze and plot the time and frequency domain characteristics of two stream data channels.

    This function takes two channel references (cr1 and cr2) and an optional stream data ID, and
    generates two plots: one showing the time-domain waveforms, and one showing the amplitude
    spectral density (ASD) in the frequency domain. The function also provides options to
    filter the data, fit a noise model, and adjust the display of the plots.

    Args:
        cr1 (str): The channel reference for the first channel to analyze, in the format 'c#r#'.
        cr2 (str): The channel reference for the second channel to analyze, in the format 'c#r#'.
        stream_data_id (int, optional): The index of the `StreamData` instance to use. If not
            provided, the most recent `StreamData` instance will be used.
        yoffset (float, optional): The vertical offset between the waveforms in the time domain plot.
        nperseg (int, optional): The number of segments to use for the Welch method when computing
            the power spectral density. Default is 10.
        fs (float, optional): The sampling frequency of the stream data, in Hz. Default is 396.332.
        sq1fb_to_pA (float, optional): The conversion factor from SQ1FB to pA. Default is 1224.23093499038.
        do_fit (bool, optional): Whether to fit a noise model to the ASD. Default is False.
        fit_freq_min (float, optional): The minimum frequency to use for the noise model fit, in Hz.
            Default is 0.02.
        fit_freq_max (float, optional): The maximum frequency to use for the noise model fit, in Hz.
            Default is 50.
        show_unfiltered (bool, optional): Whether to display the unfiltered waveforms in the time
            domain plot. Default is True.
        filter_f3db_hz (float, optional): The 3 dB cutoff frequency for the low-pass filter applied
            to the data, in Hz. Default is 1.
        p0 (list, optional): The initial parameter values for the noise model fit. Default is
            [125., 0.5, 0.1].
        bounds_low (list, optional): The lower bounds for the noise model fit parameters. Default
            is [0., 0., 0.].
        bounds_high (list, optional): The upper bounds for the noise model fit parameters. Default
            is [np.inf, np.inf, np.inf].

    Returns:
        dict: A dictionary containing the analysis results for each channel, including the time-domain
        waveforms, frequency-domain ASDs, and (if fitted) the noise model parameters.
    """
    # If no index given, load most recent dataset
    sd = StreamData._instances[stream_data_id]
    data = sd.data

    # Filter the data to remove high-frequency noise
    b, a = signal.butter(N=1, Wn=filter_f3db_hz, btype='low', fs=fs)
    zi = signal.lfilter_zi(b, a)

    # Time domain analysis
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    plt.suptitle(sd.file_name, fontsize=18)
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    results = {}
    for idx, cr in enumerate([cr1, cr2]):
        (col, row) = get_row_col(cr)
        results[cr] = {}
        results[cr]['y'] = np.array(data[col][row]) * sq1fb_to_pA
        results[cr]['t'] = (1. / fs) * (np.array(range(len(results[cr]['y']))))
        print(f"{cr} : len(y) = {len(results[cr]['y'])}")
        results[cr]['y_ms'] = results[cr]['y'] - np.mean(results[cr]['y'])
        results[cr]['y_ms_filt'] = signal.lfilter(b, a, results[cr]['y_ms'], zi=zi * results[cr]['y_ms'][0])[0]
        if show_unfiltered:
            ax1.plot(results[cr]['t'], (results[cr]['y_ms'] / 1.e3 - idx * yoffset), alpha=0.5, color=color_cycle[idx], label=f'{cr}')
        ax1.plot(results[cr]['t'], (results[cr]['y_ms_filt'] / 1.e3 - idx * yoffset), alpha=1.0, color=color_cycle[idx], label=f'{cr}')

    # Plot the difference between the two channels
    if show_unfiltered:
        ax1.plot(results[cr1]['t'], (results[cr2]['y_ms'] / 1.e3 - results[cr1]['y_ms'] / 1.e3) / np.sqrt(2) - (idx + 1) * yoffset, alpha=0.5, color=color_cycle[idx + 1], label=f'{cr2}-{cr1}')
    ax1.plot(results[cr1]['t'], (results[cr2]['y_ms_filt'] / 1.e3 - results[cr1]['y_ms_filt'] / 1.e3) / np.sqrt(2) - (idx + 1) * yoffset, alpha=1.0, color=color_cycle[idx + 1], label=f'{cr2}-{cr1}')

    ax1.set_xlabel('Time (sec)', fontsize=14)
    ylabel_ax1 = r'TES Current Eq. (pA) [SQ1FB$\rightarrow$pA=' + f'{sq1fb_to_pA:.1f}]'
    ax1.set_ylabel(ylabel_ax1, fontsize=14)

    # Frequency domain analysis
    for idx, cr in enumerate([cr1, cr2]):
        welch_nperseg = max(1, int(len(results[cr]['y_ms']) / nperseg))
        results[cr]['freq'], results[cr]['psd'] = signal.welch(results[cr]['y_ms'], nperseg=welch_nperseg, fs=fs)
        results[cr]['asd'] = np.sqrt(results[cr]['psd'])
        ax2.loglog(results[cr]['freq'], results[cr]['asd'], alpha=0.8, label=f'{cr}', color=color_cycle[idx])

    # Plot the difference between the two channels in the frequency domain
    y_ms_diff = results[cr2]['y_ms'] - results[cr1]['y_ms']
    welch_nperseg_diff = max(1, int(len(y_ms_diff) / nperseg))
    freq_diff, pxx_diff = signal.welch(y_ms_diff, nperseg=welch_nperseg_diff, fs=fs)
    asd_diff = np.sqrt(pxx_diff) / np.sqrt(2)
    ax2.loglog(freq_diff, asd_diff, alpha=0.5, label=f'({cr2}-{cr1})' + r'$/{\sqrt{2}}$', color=color_cycle[idx + 1])

    # Plot the mean ASD
    asd_mean = np.mean(np.stack([results[cr1]['asd'], results[cr2]['asd']], axis=0), axis=0)
    ax2.loglog(results[cr1]['freq'], asd_mean, c=color_cycle[idx + 2], label='mean asd', alpha=0.5)

    # Fit a noise model to the ASD
    if do_fit:
        fridx = np.where((results[cr1]['freq'] > fit_freq_min) & (results[cr1]['freq'] < fit_freq_max))
        freq_fr = results[cr1]['freq'][fridx]
        asd_fit_fr = asd_mean[fridx]
        bounds = (bounds_low, bounds_high)
        popt, pcov = optimize.curve_fit(simple_noise_model, freq_fr, asd_fit_fr, p0=p0, bounds=bounds)
        wl, n, f_knee = popt
        ax2.loglog(results[cr1]['freq'], simple_noise_model(results[cr1]['freq'], *popt), color=color_cycle[idx + 2], ls='--', lw=3, label='fit' +
                  f' white-noise level = {wl:.2f}' +
                  r' pA/$\sqrt{Hz}$,' + f' n = {n:.2f}' +
                  r', f$_{knee}$ = ' + f'{f_knee:.2f} Hz')

    ax2.set_ylabel(r'TES Current Eq. ASD (pA$/\sqrt{Hz}$)',fontsize=16)
    ax2.set_xlabel('Frequency (Hz)', fontsize=14)
    ax2.set_xlim(np.min(results[cr1]['freq']), fs / 2)

    legend_font_size = 12
    if do_fit:
        legend_font_size = 8
    ax2.legend(loc='lower left', fontsize=legend_font_size)

    plt.tight_layout()

    return results

## Should be able to incorporate effects of DDS filter
def simple_noise_model(freq, wl, n, f_knee):
    """
    Crude model for noise modeling.
   
    Args
    ----
    wl : float
        White-noise level.
    n : float
        Exponent of 1/f^n component.
    f_knee : float
        Frequency at which white noise = 1/f^n component
    """
    A = wl*(f_knee**n)
    
    # The downsample filter is at the flux ramp frequency
    #w, h = signal.freqz(filter_b, filter_a, worN=freq,
    #                    fs=flux_ramp_freq)
    #tf = np.absolute(h) # filter transfer function
    
    return (A/(freq**n) + wl)

def get_mean_raw_asd(col, idxpath, fsamp=125e6):
    """
    Compute the mean amplitude spectral density (ASD) for a list of raw waveforms.

    This function takes the path to an index file that contains the file paths to a set of
    waveform data files, and computes the mean ASD for the waveforms in the specified column.
    It also computes the root-mean-square (RMS) value of the mean ASD.

    Parameters:
    col (int): The column index of the waveforms to process.
    idxpath (str): The path to the index file containing the raw waveform data file paths.
    fsamp (float, optional): The sampling rate of the waveforms in Hz. Default is 125e6 (125 MHz).

    Returns:
    tuple:
        freqs (numpy.ndarray): The frequency axis of the ASD.
        mean_asd (numpy.ndarray): The mean ASD of the waveforms.
        rms (float): The root-mean-square value of the mean ASD.
    """
    datafiles = []
    asds = []
    freqs = None

    # Read the waveform data file paths from the index file
    with open(idxpath, 'r') as file:
        for line in file:
            processed_line = line.strip()  # Remove newline characters
            datafiles.append(processed_line)

    # Compute the ASD for each waveform and store the results
    for datafile in datafiles:
        data = np.load(datafile, allow_pickle=True)
        vampin = data.item()[col]['V@AmpIn'][0]

        # Compute the periodogram of the mean-subtracted waveform
        freqs, Pxx_den = signal.periodogram(vampin - np.mean(vampin), fsamp, scaling='density')
        asds.append(np.sqrt(Pxx_den))

    # Compute the mean ASD
    mean_asd = np.mean(np.array(asds), axis=0)

    # Compute the RMS of the mean ASD
    rms = np.sqrt(np.sum(mean_asd * mean_asd) * np.median(np.diff(freqs)))

    return freqs, mean_asd, rms

def plot_sq1curves(sq1tuneOutput, cols, rows):
    """
    Plot SQ1 tune curves for the requested rows and columns.

    This function takes the SQ1 tuning output, a list of column indices, and a list of row indices,
    and creates a plot for each requested row and column combination. The plot displays the SA FB
    (μA) vs. SQ1 FB (μA) curve, with the best bias point and the selected tune point marked.

    Parameters:
    sq1tuneOutput (dict): A dictionary containing the SQ1 tuning output data. The keys should be row
                         indices, and the values should be another dictionary containing the curve data
                         for each column.
    cols (list): A list of column indices to plot.
    rows (list): A list of row indices to plot.

    Returns:
    None
    """
    for col in cols:
        for row in rows:
            # Get the curve data for the current row and column
            sq1crdict = sq1tuneOutput[row][col]

            # Create a new figure for the current row and column
            plt.figure(tight_layout=True, figsize=(20, 10))
            plt.suptitle('SA FB (μA) vs. SQ1 FB (μA)')
            plt.title(f'Row {row} Column {col}')

            # Plot the curves for each bias value
            for bidx, bias in enumerate(sq1crdict['biasValues']):
                linewidth = 1.0
                if bidx == sq1crdict['bestIndex']:
                    linewidth = 2.0
                peak = sq1crdict['peaks'][bidx]
                phinot = sq1crdict['phinots'][bidx]
                label = f'{bias:1.3f} - P-P: {peak:1.3f} - $\\phi_o$: {phinot:.2f}'
                color = plt.gca()._get_lines.get_next_color()

                # Plot the curve
                plt.plot(sq1crdict['xValues'], sq1crdict['curves'][bidx], label=label, linewidth=linewidth, color=color)

                # Mark the max and min points
                plt.plot(*sq1crdict['highPoints'][bidx], '^', color=color)
                plt.plot(*sq1crdict['lowPoints'][bidx], 'v', color=color)

            # Plot the tune point
            plt.plot(sq1crdict['xOut'], sq1crdict['yOut'], 's', label='Tune Point')
            plt.axhline(y=sq1crdict['yOut'], linestyle='--')
            plt.axvline(x=sq1crdict['xOut'], linestyle='--')

            # Add labels and legend
            plt.xlabel('SQ1 FB (μA)', fontsize=12)
            n = len(sq1crdict['biasValues'])
            plt.legend(ncol=math.ceil(n / 10), fontsize=8, loc='lower right')
            plt.grid(True)
            plt.tight_layout()
            plt.show()

#def plot_timing(waveform_filename,stack_on=None,align_on=None):
#    if not os.path.exists(filename):
#        print(f"Error: waveform file '{filename}' not found.")
#        return
#    
#    waveform = np.load(waveform_filename,allow_pickle=True)
#
#    # Assumes ColumnBoard[0] is connected and in control
#    cb = Client.cbs[0]
#    RowPeriodCycles=cb.WarmTdmCore.Timing.TimingTx.RowPeriodCycles.value()
#    WaveformCaptureTime=cb.WarmTdmCore.Timing.TimingTx.WaveformCaptureTime.value()
#    NumRows = len(r.Group.RowIndexOrderList.get())
#    
#    # Overplot
#    plt.figure()
#    vin_uV=waveform.item()[col]['V@AmpIn'][0]*1.e6
#    ts_us=(np.arange(len(vin_uV))+WaveformCaptureTime)*(1./fadc)*1e6
#    row_period_us = (1./fadc)*1e6*RowPeriodCycles
#
#    for array_visit in range(int((np.max(ts_us)-np.min(ts_us))/(row_period_us*NumRows))):
#        idxs=np.where((ts_us-(array_visit*row_period_us*NumRows)>=0)&((ts_us-(array_visit*row_period_us*NumRows))<row_period_us*NumRows))[0]
#        plt.plot(ts_us[idxs]-(array_visit*row_period_us*NumRows),vin_uV[idxs])
#
#    plt.xlim(0,row_period_us*NumRows)
#    plt.title(f'col{col}')
#    plt.xlabel('Time ($\mu$sec)')
#    plt.ylabel('V@AmpIn ($\mu$V)')
    
