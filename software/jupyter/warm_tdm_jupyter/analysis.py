from .client import Client

import math
import numpy as np
import matplotlib.pylab as plt
from scipy import signal

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