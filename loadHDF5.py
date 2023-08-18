# make a script to open and process HDFF file for Jon
import platform

import h5py
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

data_dir = r"C:\Users\gamm5831\Documents\FPGA\TMF8828\data\ExperimentalTest\MysteryMaterial0.hdf5"
distance = 400
capture = 1
angle = 0
nameString = f'{distance}mm/{angle} degrees/Capture #{capture}/'
print(nameString)

with h5py.File(data_dir, 'r') as f:
    print(f.name)
    try:
        arr = [(f['400mm/0 degrees/Capture #1/Histograms/reference'])]
    except:
        arr = [[]]
    for i in range(1, 65):
        arr = np.append(arr, [(f[nameString+'Histograms/ch'+str(i)])], axis=0)
    conf1 = np.asarray(f[nameString+'Measurement/Confidence1'])
    dist1 = np.asarray(f[nameString+'Measurement/Distance1'])

    pltCorners = False
    rows = 1
    columns = 1
    corners = [1, 8, 57, 64]
    channels = range(9, 17)
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown', 'tab:pink', 'tab:gray']
    fig, ax = plt.subplots()

    for i in range(rows*columns):
        r = int(i / columns)
        c = i % columns
       # for ch in range(i*8 + 1, (i+1)*8 + 1): # rows
       # for ch in range(1 + i, 65 + i, 8):  # columns
        # for ch in range(33, 41):
            #   ax[r,c].plot(range(128), arr[ch+1, :], 'ks')
        ax.bar(range(128), arr[29, :], 1, alpha=0.7, edgecolor='black')
        if pltCorners:
            for n in corners:
                ax.bar(range(128), arr[n, :], 1, linestyle='--', alpha=0.5)
        # ax[r,c].set_xticks(range(0, 129, 5))
       # ax[r,c].set_xticks(range(0,129), minor=True)
        ax.set_xlim([0, 60])
       #  ax[r,c].set_ylim([0, 500])
        # ax[r,c].set_facecolor('#eafff5')
        # ax[r,c].grid(which='minor', alpha=0.2)
        # ax[r,c].grid(which='major', alpha=0.5)
        ax.set_xlabel('Bin')
        ax.set_ylabel('Photons/Bin')
        ax.set_title('Ch '+str(35))
    plt.show()










