import pickle
import numpy as np
filename = 'OrderedCsvLogScale'
with open(filename + 'Meas.pkl', 'rb') as f:
    RawData = pickle.load(f)
# with open(filename + 'header.pkl', 'rb') as f:
#     h = pickle.load(f)
# TODO: NEED TO PROCESS DATA EVERY 4 BYTES IS REVERSED IN ORDER
# processed data dict
p = {}
for capture in range(4):
    p[capture + 1] = np.array([], dtype=np.uint8)
    for word in range(32):
        for i in range(4):
            p[capture + 1] = np.append(p[capture + 1], RawData[capture][(4*word)+3-i])


confidence = {}
dist = {}
for capture in range(1, 5):
    dist[capture] = np.array([], dtype=np.uint16)
    confidence[capture] = np.array([], dtype=np.uint8)
    for zone in range(36):
        confidence[capture] = np.append(confidence[capture], p[capture][3*zone+19+1])
        dist[capture] = np.append(dist[capture], p[capture][3*zone+19+2]+(p[capture][3*zone+19+3] << 8))

sq = {
    1: np.zeros((8, 8), dtype=np.uint16),
    2: np.zeros((8, 8), dtype=np.uint16)
}
conf = {
    1: np.zeros((8, 8), dtype=np.uint8),
    2: np.zeros((8, 8), dtype=np.uint8)
}
for scc in range(2):  # sub capture column
    for scr in range(2):  # sub capture row
        for col in range(2):
            for row in range(4):
                sq[1][7 - 2 * row - scr, 4 * col + 2 * scc] = dist[1 + 2 * scr + scc][col + 2 * row]
                sq[1][7 - 2 * row - scr, 4 * col + 2 * scc + 1] = dist[1 + 2 * scr + scc][col + 2 * row + 9]
                sq[2][7 - 2 * row - scr, 4 * col + 2 * scc] = dist[1 + 2 * scr + scc][col + 2 * row + 18]
                sq[2][7 - 2 * row - scr, 4 * col + 2 * scc + 1] = dist[1 + 2 * scr + scc][col + 2 * row + 27]
                conf[1][7 - 2 * row - scr, 4 * col + 2 * scc] = confidence[1 + 2 * scr + scc][col + 2 * row]
                conf[1][7 - 2 * row - scr, 4 * col + 2 * scc + 1] = confidence[1 + 2 * scr + scc][col + 2 * row + 9]
                conf[2][7 - 2 * row - scr, 4 * col + 2 * scc] = confidence[1 + 2 * scr + scc][col + 2 * row + 18]
                conf[2][7 - 2 * row - scr, 4 * col + 2 * scc + 1] = confidence[1 + 2 * scr + scc][col + 2 * row + 27]
for measurement in range(1,3):
    for row in range(8):
        for col in range(8):
            if conf[measurement][row, col] < 0:
                sq[measurement][row, col] = 0
print('Distance 1')
print(sq[1])
print('Confidence 1')
print(conf[1])
print(' ')
print('Distance 2')
print(sq[2])
print('Confidence 2 ')
print(conf[2])


# import pickle
# for i in range(1,5):
#    with open('data'+str(i)+'.pkl', 'wb') as f:
#       pickle.dump('data'+str(i), f)

