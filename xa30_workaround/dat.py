import numpy as np
import sys

def dat_to_array(dat_files, shape):
    # frame_list
    frame_list = []
    for dat_path in sorted(dat_files):
        # read binary file
        with open(dat_path, "rb") as f:
            binary_data = f.read()

        # convert to numpy array
        data = np.frombuffer(binary_data, dtype=np.uint16)
        try:
            data = data.reshape(*shape)
        except ValueError:
            tb = sys.exception().__traceback__
            raise RuntimeError(f"ERROR: cannot reshape array of size {data.shape} into shape {shape}. ").with_traceback(tb)
        num_slices = data.shape[1]

        # TODO: this should be determined from the slice timing but for now we will assume
        # interleaved slices
        indices = np.argsort(np.concatenate((np.arange(1, num_slices, 2), np.arange(0, num_slices, 2))))

        # reindex slices
        data = data[:, indices, :, :]
        # TODO: we should probably do multiple orientation checks to make sure this is correct
        data = np.flip(np.moveaxis(data, [0, 1, 2, 3], [3, 2, 1, 0]), 1)

        # append to frame list
        frame_list.append(data)
    data = np.stack(frame_list, axis=-1)
    return data
