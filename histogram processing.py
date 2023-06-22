import pickle
import numpy as np
import os
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('TkAgg')

filter_reference = True  # whether the processed csv and graph include reference file
filename = 'blank1'
with open(filename + 'Hist.pkl', 'rb') as f:
    RawData = pickle.load(f)
# remember every 4 bytes still reversed

histRaw = {}  # combine LSB, mid-byte, and MSB for each channel
for i in range(8):
    if filter_reference:
        a = 1
    else:
        a = 0
    for n in range(a, 9):
        histRaw[i * 10 + n] = np.array([], dtype=np.uint32)
        for b in range(128):
            tempData = RawData[n + 30 * i][b] + (RawData[n + 30 * i + 10][b] << 8) + (RawData[n + 30 * i + 20][b] << 16)
            histRaw[i*10 + n] = np.append(histRaw[i*10 + n], tempData)


histOrdered = {}
for channel in histRaw:
    histOrdered[channel] = np.array([], dtype=np.uint32)
    for word in range(32):
        for i in range(4):
            histOrdered[channel] = np.append(histOrdered[channel], histRaw[channel][(4*word)+3-i])
print(histOrdered)




tempArr = []
for l in histOrdered:
    tempArr.append(','.join(map(str, histOrdered[l])))
outString = '\n'.join(tempArr)
hist_dir = r"C:\Users\gamm5831\Documents\FPGA\TMF8828\data\\"
fileString = '1meter'
# names the file in the following format: "fileString#",
i = 0
while os.path.exists(hist_dir + fileString + "%s.csv" % i):
    i = i + 1
file_name = hist_dir + fileString + "%s.csv" % i
file = open(file_name, 'w')
file.write(outString)
file.close()
print(f"data saved to csv: {file_name}")


file_name = os.path.join(hist_dir, fileString + str(i) + ".csv")
file = open(file_name, 'r')
out = file.read()
file.close()

out = out.replace('\n', ',')
out = out.split(',')
new_out = []
for i in range(len(out)):
    try:
        new_out.append(float(out[i]))
    except (ValueError, TypeError):
        pass
new_out = np.array_split(new_out, len(new_out)/128)
hist_data_arr = {}
for tdc in range(len(new_out)):
    hist_data_arr[tdc] = np.array([], dtype=np.float32)
    hist_data_arr[tdc] = np.append(hist_data_arr[tdc], new_out[tdc])

fig, ax = plt.subplots()
for i in range(len(new_out)):
    ax.plot(hist_data_arr[i])
plt.show()
