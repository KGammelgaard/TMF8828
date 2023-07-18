import logging
import platform
import os, sys
import pickle
import time
import h5py
from time import sleep
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

h5py.get_config().track_order = True  # keeps channels in the loaded order

sys.path.append('C:\\Users\\gamm5831\\Documents\\FPGA\\covg_fpga\\python\\')
from pyripherals.core import FPGA

matplotlib.use('TkAgg')
plt.ion()

sys.path.append('C:\\Users\\gamm5831\\Documents\\FPGA\\TMF8828')



hex_dir = 'C:\\Users\\gamm5831\\Documents\\FPGA\\TMF8828'
hist_dir = r"C:\Users\gamm5831\Documents\FPGA\TMF8828\data\DPeaks\\"
# bl: boot-loader commands, read .hex file and process line by line.
HISTCAP = True  # whether histograms are captures
MEASURE = True  # whether measurement data is processed and collected
LOGARITHMIC = True  # logarithmic confidence scaling


def bl_intel_hex(hex_dir, filename='tmf8x2x_application_patch.hex'):
    """ read intel HEX file line by line
    Parameters
    ----------
    hex_dir : string
        directory of the hex file
    filename : string
        name of the hex file

    Returns
    -------
    line_list : list
        list of each line in the file

    """

    with open(os.path.join(hex_dir, filename), 'r') as f:
        line_list = [l for l in f]

    return line_list


def bl_checksum(data):
    """ create checksum as described in section 6.3
        of the host driver manual (AN000597)

    Parameters
    ----------
    data : list
        bytes that will be sent

    Returns
    -------
    ones_comp : int
        list of each line in the file
    """

    low_byte = sum(data) & 0xff  # only use lowest byte of sum
    ones_comp = low_byte ^ 0xff  # ones complement op. via XOR
    return ones_comp


def bl_process_line(l):
    """
    interpret a HEX record line and prepare for i2c write

    Parameters
    ----------
    l : string
        a line from the HEX record

    Returns
    -------
    data : list
        list of bytes to write
    """

    # https://en.wikipedia.org/wiki/Intel_HEX

    cmd_addr = 0x08
    ram_addr_cmd = 0x43
    data_cmd = 0x41

    # data command
    if l[7:9] == '00':
        data = l[9:]
        data = data.strip()[:-2]
        data_bytes = bytearray.fromhex(data)
        data_len = len(data_bytes)
        data = [cmd_addr, data_cmd, data_len] + list(data_bytes)

    # extended address
    elif l[7:9] == '04':
        addr = l[9:13]
        addr_bytes = bytearray.fromhex('0' + addr + '0')
        data_len = 0
        data = [cmd_addr, ram_addr_cmd] + list(addr_bytes)

    else:
        return None

    data.append(bl_checksum(data[1:]))

    return data


bl_hex_lines = bl_intel_hex(hex_dir, filename='tmf8x2x_application_patch.hex')
print(f'RAM patch is {len(bl_hex_lines)} lines long')

sys.path.insert(0, r'C:\Users\gamm5831\Documents\FPGA\covg_fpga\python')

from boards import TOF
# Initialize FPGA
f = FPGA()
f.init_device()

# Instantiate the TMF8801 controller.
tof = TOF(f)

logging.basicConfig(filename='DAC53401_test.log',
                    encoding='utf-8', level=logging.INFO)


# check ID
id = tof.TMF.get_id()
print(f'Chip id 0x{id:04x}')
appid = tof.TMF.read_by_addr(0x00)
print(f'In app {appid}')
print(f'CPU ready? {tof.TMF.cpu_ready()}')

tof.TMF.download_init()
status = tof.TMF.ram_write_status()
print(f'RAM write status: {status}')

for l in bl_hex_lines:
    d = bl_process_line(l)
    if d is not None:
        addr = d[0]
        data = d[1:]

        tof.TMF.i2c_write_long(tof.TMF.ADDRESS,
            [addr],
            (len(data)),
            data)
        # reads back 3 bytes from 'CMD_DATA7'
        status = tof.TMF.ram_write_status()
        # TODO: check that status is 00,00,FF
        # TODO: consider skipping status check to reduce time for upload
        # if not (status == [0,0,0xFF]):
        #     print(f'Bootloader status unexpected value of {status}')

tof.TMF.ramremap_reset()

for i in range(3):
    print(f'CPU ready? {tof.TMF.cpu_ready()}')
if HISTCAP or MEASURE or LOGARITHMIC:
    tof.TMF.write(0x16, 'CMD_DATA7')
    sleep(0.02)
    if HISTCAP:
        print('ENABLING HISTOGRAM CAPTURE')
        tof.TMF.write(0x01, '8828HIST_DUMP')
        sleep(0.02)
    if not MEASURE:
        print('DISABLING MEASUREMENT CAPTURE')
        temp = tof.TMF.read_by_addr(0x35)
        temp[0] &= ~(0x04)  # set the mask with distance bit cleared to not measure
        tof.TMF.write(temp[0], '8828AKG_SETTINGS')
        sleep(0.02)
    if LOGARITHMIC:
        print('ENABLING LOGARITHMIC CONFIDENCE SCALING')
        temp = tof.TMF.read_by_addr(0x35)
        temp[0] |= 0x80  # set the mask with log bit set to log scale conf
        tof.TMF.write(temp[0], '8828AKG_SETTINGS')
    sleep(0.02)
    tof.TMF.write(0x15, 'CMD_DATA7')
    print('READY TO MEASURE')


def save_data(name):
    """
       reads and saves data for a measurement
       does not send the command to measure

       Parameters
       ----------
       name : string
           name of pkl file

       Returns
       -------
       data : none
       """
    h = {}
    d = {}
    for i in range(1, 5):
        stat = tof.TMF.read_by_addr(0xe1)
        print('loop ' + str(i) + ' initial ' + str(stat[0]))
        tof.TMF.write(stat[0], 'INT_STATUS')
        stat = tof.TMF.read_by_addr(0xe1)
        print('loop ' + str(i) + ' cleared ' + str(stat[0]))
        h['h' + str(i)] = tof.TMF.read_by_addr(0x20, num_bytes=4)
        buf, e = tof.TMF.i2c_read_long(tof.TMF.ADDRESS, [0x24], data_length=128, data_transfer='pipe')
        d['d' + str(i)] = np.asarray(buf)
    with open(name + '.pkl', 'wb') as b:
        pickle.dump(d, b)
    with open(name + 'header.pkl', 'wb') as b:
        pickle.dump(h, b)


def empty_data():
    """
        clears out data registers of junk from previous measurement
    Returns
    -------
    none
    """
    cnt_limit = 10
    cnt = 0
    bit_1 = 0  # int bit for measurement
    bit_3 = 0  # int bit for histogram
    while cnt < cnt_limit:
        st = tof.TMF.read_by_addr(0xE1)
        bit_3 = st[0] & 0x08
        bit_1 = st[0] & 0x02
        if bit_3:
            tof.TMF.write(st[0], 'INT_STATUS')
            buf, e = tof.TMF.i2c_read_long(tof.TMF.ADDRESS, [0x27], data_length=128, data_transfer='pipe')
            cnt = 0
        elif bit_1:
            tof.TMF.write(st[0], 'INT_STATUS')
            buf, e = tof.TMF.i2c_read_long(tof.TMF.ADDRESS, [0x24], data_length=128, data_transfer='pipe')
            cnt = 0
        cnt = cnt + 1
        sleep(0.2)


def save_histogram():
    """
       reads and returns raw histograms fata
       sends command to measure
       does not record header or sub-header

       Returns
       -------
       data : dictionary of raw Histogram data and dictionary of raw measurement data
       """
    hist = {}
    measure = {}
    start_time = time.time()
    tof.TMF.write(0x10, 'CMD_DATA7')
    sleep(0.01)
    for sub in range(4):
        cnt = 0
        bit_3 = 0
        bit_1 = 0
        cnt_limit = 100
        for i in range(60):
            while (cnt < cnt_limit) and (bit_3 == 0):  # checks if bit_3 has changed
                st = tof.TMF.read_by_addr(0xe1)
                bit_3 = st[0] & 0x08  # check bit 3
                cnt = cnt + 1
                if cnt == cnt_limit:
                    print('Timeout waiting for INT4 HIST')
            print(str(time.time() - start_time))
            tof.TMF.write(st[0], 'INT_STATUS')
            buf, e = tof.TMF.i2c_read_long(tof.TMF.ADDRESS, [0x27], data_length=128, data_transfer='pipe')
            hist[i + sub*60] = np.asarray(buf)
            print(str(time.time() - start_time))
        cnt = 0
        while (cnt < cnt_limit) and (bit_1 == 0):  # checks if bit_1 has changed
            st = tof.TMF.read_by_addr(0xe1)
            bit_1 = st[0] & 0x02  # check bit 1 (int2 bit)
            cnt = cnt + 1
            if cnt == cnt_limit:
                print('Timeout waiting for INT2 MEAS')
        print(str(time.time() - start_time))
        tof.TMF.write(st[0], 'INT_STATUS')
        buf, e = tof.TMF.i2c_read_long(tof.TMF.ADDRESS, [0x24], data_length=128, data_transfer='pipe')
        measure[sub] = np.asarray(buf)
        print(str(time.time() - start_time))
    tof.TMF.write(0xff, 'CMD_DATA7')
    stop_time = time.time()
    print('TIME TO CAPTURE:' + str(stop_time - start_time) + ' sec')
    return hist, measure


def process_measurement(RawMeasure):
    """

    Parameters
    ----------
    RawMeasure : Dict
        dictionary with raw measurement values for all channels reference and unused included

    Returns
    -------
    first/second : dict
        returns 2 dicts q for first and second distance each with and 8x8 distance and confidence array
    conf
    """

    p = {}
    for capture in range(4):
        p[capture + 1] = np.array([], dtype=np.uint8)
        for word in range(32):
            for i in range(4):
                p[capture + 1] = np.append(p[capture + 1], RawMeasure[capture][(4*word)+3-i])

    confidence = {}
    dist = {}
    for capture in range(1, 5):
        dist[capture] = np.array([], dtype=np.uint16)
        confidence[capture] = np.array([], dtype=np.uint8)
        for zone in range(36):
            confidence[capture] = np.append(confidence[capture], p[capture][3*zone+19+1])
            dist[capture] = np.append(dist[capture], p[capture][3*zone+19+2]+(p[capture][3*zone+19+3] << 8))

    first = {
        'Distance': np.zeros((8, 8), dtype=np.uint16),
        'Confidence': np.zeros((8, 8), dtype=np.uint8)
    }
    second = {
        'Distance': np.zeros((8, 8), dtype=np.uint16),
        'Confidence': np.zeros((8, 8), dtype=np.uint8)
    }
    for scc in range(2):  # sub capture column
        for scr in range(2):  # sub capture row
            for col in range(2):
                for row in range(0, 8, 2):
                    column = 4 * col + 2 * scc
                    arow = 7 - row - scr
                    first['Distance'][arow, column] = dist[1 + 2 * scr + scc][col + row]
                    first['Distance'][arow, column + 1] = dist[1 + 2 * scr + scc][col + row + 9]
                    second['Distance'][arow, column] = dist[1 + 2 * scr + scc][col + row + 18]
                    second['Distance'][arow, column + 1] = dist[1 + 2 * scr + scc][col + row + 27]
                    first['Confidence'][arow, column] = confidence[1 + 2 * scr + scc][col + row]
                    first['Confidence'][arow, column + 1] = confidence[1 + 2 * scr + scc][col + row + 9]
                    second['Confidence'][arow, column] = confidence[1 + 2 * scr + scc][col + row + 18]
                    second['Confidence'][arow, column + 1] = confidence[1 + 2 * scr + scc][col + row + 27]
    return first, second


def process_histogram(RawData, filter_reference=False):
    """

    Parameters
    ----------
    RawData : dict
        raw data from histogram readout
    filter_reference : bool
        whether to filter out reference channel for returned dataset

    Returns
    -------
    histReordered : list
        list with histogram data for each channel in order of ROIs from left to right top to bottom
        histReordered[0] is a reference if included
    """
    histRaw = {}  # combine LSB, mid-byte, and MSB for each channel
    for i in range(8):
        if filter_reference:
            a = 1
        else:
            a = 0
        for n in range(a, 9):
            histRaw[i * 10 + n] = np.array([], dtype=np.uint32)
            for b in range(128):
                tempData = RawData[n + 30 * i][b] + (RawData[n + 30 * i + 10][b] << 8) + (
                            RawData[n + 30 * i + 20][b] << 16)
                histRaw[i * 10 + n] = np.append(histRaw[i * 10 + n], tempData)

    histOrdered = {}
    for channel in histRaw:
        histOrdered[channel] = np.array([], dtype=np.uint32)
        for word in range(32):
            for i in range(4):
                histOrdered[channel] = np.append(histOrdered[channel], histRaw[channel][(4 * word) + 3 - i])

    histReordered = []
    if not filter_reference:
        histReordered.append(histOrdered[0])
    for r in [7, 5, 3, 1]:
        for sr in [40, 41, 0, 1]:
            for c in range(0, 40, 10):
                histReordered.append(histOrdered[r + sr + c])
    return histReordered


def capture_to_HDF5(fileString, data_dir=hist_dir):
    print('Describe Capture Scene: ')
    scene_desc = input()
    hist, meas = save_histogram()
    first, second = process_measurement(meas)
    orderedHist = list(process_histogram(hist))
    # names the file in the following format: "fileString#",
    i = 0
    while os.path.exists(data_dir + fileString + "%s.hdf5" % i):
        i = i + 1
    file_name = data_dir + fileString + "%s.hdf5" % i
    with h5py.File(file_name, 'w') as f:
        histGroup = f.create_group('Histograms')
        measGroup = f.create_group('Measurement')
        histGroup.create_dataset('reference', (128,), dtype=np.uint32, data=orderedHist[0])
        h = []
        for i in range(1, len(orderedHist)):
            h.append(histGroup.create_dataset('ch'+str(i), (128,), dtype=np.uint32, data=orderedHist[i]))
        measGroup.create_dataset('Distance1', (8, 8), dtype=np.uint32, data=first['Distance'])
        measGroup.create_dataset('Confidence1', (8, 8), dtype=np.uint32, data=first['Confidence'])
        measGroup.create_dataset('Distance2', (8, 8), dtype=np.uint32, data=second['Distance'])
        measGroup.create_dataset('Confidence2', (8, 8), dtype=np.uint32, data=second['Confidence'])
        # all data loaded in now apply attributes
        for c in range(8):
            for r in range(8):
                h[r + 8 * c].attrs.create('distance1', first['Distance'][r, c])
                h[r + 8 * c].attrs.create('confidence1', first['Confidence'][r, c])
                h[r + 8 * c].attrs.create('distance2', second['Distance'][r, c])
                h[r + 8 * c].attrs.create('confidence2', second['Confidence'][r, c])
        tof.TMF.write(0x16, 'CMD_DATA7')
        sleep(0.02)
        config = tof.TMF.read_by_addr(0x24, num_bytes=4)
        if tof.TMF.read_by_addr(0x35)[0] & 0x80:
            f.attrs.create('ConfidenceScaling', 'Logarithmic')
        else:
            f.attrs.create('ConfidenceScaling', 'Linear')
        period = config[0] + (config[1] << 8)
        kIterations = config[2] + (config[3] << 8)
        f.attrs.create('PeriodMs', period)
        f.attrs.create('KiloIterations', kIterations)
        f.attrs.create('date', time.asctime())
        f.attrs.create('SceneDescription', scene_desc)
        f.attrs.create('Device', 'TMF8828')
        f.attrs.create('Python Version', platform.python_version())
        tof.TMF.write(0xff, 'CMD_DATA7')


def write_hist(hist_data_arr, fileString, hist_dir=hist_dir):
    tempArr = []
    for l in range(len(hist_data_arr)):
        tempArr[l] = ','.join(map(str, hist_data_arr[l]))
    outString = '\n'.join(tempArr)

    # names the file in the following format: "fileString#",
    i = 0
    while os.path.exists(hist_dir + fileString + "%s.csv" % i):
        i = i + 1
    file_name = hist_dir + fileString + "%s.csv" % i
    file = open(file_name, 'w')
    file.write(outString)
    file.close()
    print(f"data saved to csv: {file_name}")


def read_hist(hist_num, material, directory=hist_dir):

    file_name = os.path.join(directory, material + str(hist_num) + ".csv")
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
    return hist_data_arr


def plot_hist(hist_data_arr):
    fig, ax = plt.subplots()
    for i in range(len(hist_data_arr)):
        ax.plot(hist_data_arr[i])
    plt.show()
