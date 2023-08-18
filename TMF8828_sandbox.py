import logging
import platform
import os, sys
import pickle
import time
import h5py
import serial
from time import sleep
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import serial
from pyripherals.peripherals.TMF8828 import TMF8828
import copy

h5py.get_config().track_order = True  # keeps channels in the loaded order


from pyripherals.core import FPGA, Endpoint

matplotlib.use('TkAgg')
plt.ion()

sys.path.append('C:\\Users\\gamm5831\\Documents\\FPGA\\TMF8828')



hex_dir = 'C:\\Users\\gamm5831\\Documents\\FPGA\\TMF8828'
hist_dir = r"C:\Users\gamm5831\Documents\FPGA\TMF8828\data\ExperimentalTest\\"

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

sys.path.insert(0, r'C:\Users\gamm5831\Documents\FPGA\tof_fpga\python')

# Assign I2CDAQ busses
Endpoint.I2CDAQ_level_shifted = Endpoint.get_chip_endpoints('I2CDAQ')
# We want the endpoints_from_defines to be the same make a copy before incrementing
Endpoint.I2CDAQ_QW = Endpoint.advance_endpoints(
    endpoints_dict=copy.deepcopy(Endpoint.I2CDAQ_level_shifted))

# Initialize FPGA
f = FPGA()
f.init_device()

# Instantiate the TMF8801 controller.
tof = TMF8828(fpga=f, addr_pins=0x00, endpoints=Endpoint.I2CDAQ_QW)

logging.basicConfig(filename='DAC53401_test.log',
                    encoding='utf-8', level=logging.INFO)
# check ID
id = tof.get_id()
print(f'Chip id 0x{id:04x}')
appid = tof.read_by_addr(0x00)
print(f'In app {appid}')
print(f'CPU ready? {tof.cpu_ready()}')

tof.download_init()
status = tof.ram_write_status()
print(f'RAM write status: {status}')

for l in bl_hex_lines:
    d = bl_process_line(l)
    if d is not None:
        addr = d[0]
        data = d[1:]

        tof.i2c_write_long(tof.ADDRESS,
            [addr],
            (len(data)),
            data)
        # reads back 3 bytes from 'CMD_DATA7'
        status = tof.ram_write_status()
        # TODO: check that status is 00,00,FF
        # TODO: consider skipping status check to reduce time for upload
        # if not (status == [0,0,0xFF]):
        #     print(f'Bootloader status unexpected value of {status}')

tof.ramremap_reset()

for i in range(3):
    print(f'CPU ready? {tof.cpu_ready()}')
if HISTCAP or MEASURE or LOGARITHMIC:
    tof.write(0x16, 'CMD_STAT')
    sleep(0.02)
    if HISTCAP:
        print('ENABLING HISTOGRAM CAPTURE')
        tof.write(0x01, 'HIST_DUMP')
        sleep(0.02)
    if not MEASURE:
        print('DISABLING MEASUREMENT CAPTURE')
        temp = tof.read_by_addr(0x35)
        temp[0] &= ~(0x04)  # set the mask with distance bit cleared to not measure
        tof.write(temp[0], 'ALG_SETTING')
        sleep(0.02)
    if LOGARITHMIC:
        print('ENABLING LOGARITHMIC CONFIDENCE SCALING')
        temp = tof.read_by_addr(0x35)
        temp[0] |= 0x80  # set the mask with log bit set to log scale conf
        tof.write(temp[0], 'ALG_SETTING')
    tof.write(0x04, 'POWER_CFG')
    tof.write(0x0a, 'INT_ENAB')
    sleep(0.02)
    tof.write(0x15, 'CMD_STAT')
    print('READY TO MEASURE')
    

def save_histogram(START=True, STOP=True):
    """
       reads and returns raw histograms fata
       sends command to measure
       does not record header or sub-header

       START : bool
            Whether the command to start a measurement is sent
       STOP : bool
            Whether the command to stop a measurement is sent

       Returns
       -------
       data : dictionary of raw Histogram data and dictionary of raw measurement data
       """
    hist = {}
    measure = {}
    subcapture = {}
    start_time = time.time()
    try:
        tof.endpoints['REPEAT_RESET']
        tof.endpoints['REPEAT_START']
    except KeyError as e:
        raise KeyError(
            'i2c_receive requires the I2C endpoints REPEAT_RESET and REPEAT_START. One or both are missing.')
    tof.fpga.xem.ActivateTriggerIn(tof.endpoints['REPEAT_RESET'].address, tof.endpoints['REPEAT_RESET'].bit_index_low)
    if START:
        tof.write(0x10, 'CMD_STAT')
        sleep(0.1)
    buf, e = tof.i2c_repeat_receive(tof.ADDRESS, [0x23], data_length=132)
    rawData = np.asarray(buf)
    splitData = np.split(rawData, 244)

    for sub in range(4):
        for i in range(60):
            hist[i+60*sub] = splitData[i + 61*sub]
        measure[sub] = splitData[60 + sub*61]
    if STOP:
        tof.write(0xff, 'CMD_STAT')
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
        for word in range(int(len(RawMeasure[0])/4)):
            for i in range(4):
                p[capture + 1] = np.append(p[capture + 1], RawMeasure[capture][(4*word)+3-i])

    confidence = {}
    dist = {}
    for capture in range(1, 5):
        dist[capture] = np.array([], dtype=np.uint16)
        confidence[capture] = np.array([], dtype=np.uint8)
        for zone in range(36):
            confidence[capture] = np.append(confidence[capture], p[capture][3*zone+19+2])
            dist[capture] = np.append(dist[capture], p[capture][3*zone+19+3]+(p[capture][3*zone+19+4] << 8))

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
    temp = {}
    if len(RawData[0]) == 132:
        for i in range(len(RawData)):
            temp[i] = RawData[i][4:132]


    histRaw = {}  # combine LSB, mid-byte, and MSB for each channel
    for i in range(8):
        if filter_reference:
            a = 1
        else:
            a = 0
        for n in range(a, 9):
            histRaw[i * 10 + n] = np.array([], dtype=np.uint32)
            for b in range(128):
                tempData = temp[n + 30 * i][b] + (temp[n + 30 * i + 10][b] << 8) + (
                            temp[n + 30 * i + 20][b] << 16)
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
        tof.write(0x16, 'CMD_STAT')
        sleep(0.02)
        config = tof.read_by_addr(0x24, num_bytes=4)
        if tof.read_by_addr(0x35)[0] & 0x80:
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
        tof.write(0x15, 'CMD_STAT')
        sleep(0.02)
        tof.write(0xff, 'CMD_STAT')


def captureLargeSample(fileString, data_dir=hist_dir):
    matDesc = input('Describe Capture Material: ')
    lighting = input('Describe the room lighting')
    i = 0
    while os.path.exists(data_dir + fileString + "%s.hdf5" % i):
        i = i + 1
    file_name = data_dir + fileString + "%s.hdf5" % i  # find free filename

    ser = serial.Serial('COM3', 9600)
    stepSize = 53.3 / 1.8  # steps per degree

    distances = [300, 305, 310, 315, 320, 325, 400, 405, 410, 415, 420, 425, 500, 505, 510, 515, 520, 525]
    angles = range(-45, 50, 5)
    f = h5py.File(file_name, 'w')
    tof.write(0x10, 'CMD_STAT')
    for d in distances:
        ser.write(str(0 * stepSize).encode())
        print(f'Place the sample {d}mm away from the optical center of the sensor')
        input('Press ENTER to continue')
        for a in angles:
            pos = str(a * stepSize)
            ser.write(pos.encode())
            if a == angles[0]:
                sleep(14)
            else:
                sleep(3)
            for capture in range(3):
                path = str(d) + 'mm/' + str(a) + ' degrees/Capture #' + str(capture + 1)
                cap = f.create_group(path)
                hist, meas = save_histogram(START=False, STOP=False)
                first, second = process_measurement(meas)
                orderedHist = list(process_histogram(hist))
                histGroup = cap.create_group('Histograms')
                measGroup = cap.create_group('Measurement')
                histGroup.create_dataset('reference', (128,), dtype=np.uint32, data=orderedHist[0])
                h = []
                for i in range(1, len(orderedHist)):
                    h.append(histGroup.create_dataset('ch' + str(i), (128,), dtype=np.uint32, data=orderedHist[i]))
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
    tof.write(0xff, 'CMD_STAT')
    sleep(0.01)
    tof.write(0x16, 'CMD_STAT')
    sleep(0.02)
    config = tof.read_by_addr(0x24, num_bytes=4)
    if tof.read_by_addr(0x35)[0] & 0x80:
        f.attrs.create('ConfidenceScaling', 'Logarithmic')
    else:
        f.attrs.create('ConfidenceScaling', 'Linear')
    period = config[0] + (config[1] << 8)
    kIterations = config[2] + (config[3] << 8)
    f.attrs.create('PeriodMs', period)
    f.attrs.create('KiloIterations', kIterations)
    f.attrs.create('date', time.asctime())
    f.attrs.create('Material Description', matDesc)
    f.attrs.create('Device', 'TMF8828')
    f.attrs.create('Python Version', platform.python_version())
    f.attrs.create('Lighting', lighting)
    tof.write(0x15, 'CMD_STAT')
    sleep(0.02)
    tof.write(0xff, 'CMD_STAT')
    f.close()
    ser.write(str(0 * stepSize).encode())
    ser.close()
    print('Data Capture Complete!') 


def i2cDataTest():
    """
    Testing repeated reads of a single register to see if it errors over 5 minutes of continuous reads
    Returns
    -------

    """
    waitTime = 0.0001  # tenth of a ms
    for i in range(int(300/waitTime)):
        data = tof.read('PATCH')
        if data != 52:
            print('Data was incorrectly received')
            return 0
        print('Good Read: ' + str(i))
        sleep(waitTime)
    print("SUCCESS")
    return 0


