# make a script to open and process HDFF file for Jon
import platform

import h5py
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

data_dir = r"C:\Users\gamm5831\Documents\FPGA\TMF8828\data\DPeaks\NoLens0.hdf5"

with h5py.File(data_dir, 'r') as f:
    try:
        arr = [(f['Histograms/reference'])]
    except:
        arr = [[]]
    for i in range(1, 65):
        arr = np.append(arr, [(f['Histograms/ch'+str(i)])], axis=0)
    conf1 = np.asarray(f['Measurement/Confidence1'])
    dist1 = np.asarray(f['Measurement/Distance1'])

    pltCorners = False
    rows = 2
    columns = 4
    corners = [1, 8, 57, 64]
    channels = range(9, 17)
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown', 'tab:pink', 'tab:gray']
    fig, ax = plt.subplots(rows, columns)

    for i in range(rows*columns):
        r = int(i / columns)
        c = i % columns
       # for ch in range(i*8 + 1, (i+1)*8 + 1): # rows
       # for ch in range(1 + i, 65 + i, 8):  # columns
        # for ch in range(33, 41):
            #   ax[r,c].plot(range(128), arr[ch+1, :], 'ks')
        ax[r,c].plot(range(128), arr[i+33, :], alpha=0.7, color = colors[i])
        if pltCorners:
            for n in corners:
                ax[r,c].plot(range(128), arr[n, :], linestyle='--', alpha=0.5)
        ax[r,c].set_xticks(range(0, 129, 5))
        ax[r,c].set_xticks(range(0,129), minor=True)
        ax[r,c].set_xlim([20, 37])
        ax[r,c].set_ylim([0, 500])
        # ax[r,c].set_facecolor('#eafff5')
        ax[r,c].grid(which='minor', alpha=0.2)
        ax[r,c].grid(which='major', alpha=0.5)
        ax[r,c].set_xlabel('Bin')
        ax[r,c].set_ylabel('Photons/Bin')
        ax[r,c].set_title('Ch '+str(i+33))
    plt.tight_layout()
    plt.show()










