# make a script to open and process HDFF file for Jon
import platform

import h5py
import numpy as np

data_dir = r"C:\Users\gamm5831\Documents\FPGA\TMF8828\data\FlatBoard0.hdf5"

with h5py.File(data_dir, 'r') as f:
    try:
        arr = [(f['Histograms/reference'])]
    except:
        arr = [[]]
    for i in range(1, 64):
        arr = np.append(arr, [(f['Histograms/ch'+str(i)])], axis=0)
    conf1 = np.asarray(f['Measurement/Confidence1'])
    dist1 = np.asarray(f['Measurement/Distance1'])









