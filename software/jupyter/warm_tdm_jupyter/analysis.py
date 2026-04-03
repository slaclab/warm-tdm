from .client import Client
from .data import StreamData
from .utils import get_row_col

import math
import numpy as np
import matplotlib.pylab as plt
from matplotlib.text import Text
from scipy import signal, optimize

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
        results[cr]['freq'], results[cr]['psd'] = signal.welch(results[cr]['y_ms'], nperseg=len(results[cr]['y_ms']) / nperseg, fs=fs)
        results[cr]['asd'] = np.sqrt(results[cr]['psd'])
        ax2.loglog(results[cr]['freq'], results[cr]['asd'], alpha=0.8, label=f'{cr}', color=color_cycle[idx])

    # Plot the difference between the two channels in the frequency domain
    y_ms_diff = results[cr2]['y_ms'] - results[cr1]['y_ms']
    freq_diff, pxx_diff = signal.welch(y_ms_diff, nperseg=len(y_ms_diff) / nperseg, fs=fs)
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

    ax2.set_ylabel(r'TES Current Eq. ASD (pA$/\sqrt{Hz}$))',fontsize=16)
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