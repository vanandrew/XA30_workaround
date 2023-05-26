import numpy as np
from pathlib import Path
import simplebrainviewer as sbv
from natsort import natsorted

# shape
shape = (5, 72, 110, 110)

# interleave indices
indices = np.argsort(np.concatenate((np.arange(1, 72, 2), np.arange(0, 72, 2))))

# load data
data_path = Path("Phantom_ME_full")

# frame_list
frame_list = []
for dat_path in natsorted(data_path.glob("Phantom_ME_full_BOLD_NORDIC_ME5_2mm_run2_Mag_*.dat")):
    print(dat_path)
    # read binary file
    with open(dat_path, "rb") as f:
        binary_data = f.read()

    # convert to numpy array
    data = np.frombuffer(binary_data, dtype=np.uint16)
    data = data.reshape(*shape)
    data = np.moveaxis(data, [0, 1, 2, 3], [0, 1, 3, 2])

    # reindex slices
    data = data[:, indices, :, :].T
    frame_list.append(data)
data = np.stack(frame_list, axis=-1)
sbv.plot_brain(data[..., 0, :])
