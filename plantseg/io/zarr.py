"""
Reading and writing zarrs. Created in the same format as h5.py
Author: Samia Mohinta
Affiliation: Cardona lab, Cambridge University
"""
import warnings
from typing import Optional, Union

import zarr
import numpy as np
from pathlib import Path

# allowed zarr keys
ZARR_EXTENSIONS = [".zarr"]
ZARR_KEYS = ["raw", "predictions", "segmentation"]


def read_zarr_voxel_size(f, zarrkey: str) -> list[float, float, float]:
    """
    :returns the voxels size stored in a zarr dataset (if absent returns [1, 1, 1])
    """
    ds = f[zarrkey]

    # parse voxel_size
    if 'element_size_um' in ds.attrs:
        voxel_size = ds.attrs['element_size_um']
    elif 'resolution' in ds.attrs:
        voxel_size = ds.attrs['resolution']
    else:
        warnings.warn('Voxel size not found, returning default [1.0, 1.0. 1.0]', RuntimeWarning)
        voxel_size = [1.0, 1.0, 1.0]

    return voxel_size


def _find_input_key(zarr_file) -> str:
    f"""
    returns the first matching key in ZARR_KEYS or only one dataset is found the key to that dataset
    """
    found_datasets = []

    def visitor_func(name, node):
        if isinstance(node, zarr.core.Array):
            found_datasets.append(name)

    zarr_file.visititems(visitor_func)

    if not found_datasets:
        raise RuntimeError(f"No datasets found - verify'{zarr_file.tree()}'")

    if len(found_datasets) == 1:
        return found_datasets[0]
    else:
        for zarr_key in ZARR_KEYS:
            if zarr_key in found_datasets:
                return zarr_key

        raise RuntimeError(f"Ambiguous datasets '{found_datasets}' in {zarr_file}. "
                           f"plantseg expects only one dataset to be present in input Zarr.")


def load_zarr(path: str,
              key: str,
              slices: Optional[slice] = None,
              info_only: bool = False) -> Union[tuple, tuple[np.array, tuple]]:
    """
    Load a dataset from a zarr file and returns some meta info about it.
    Args:
        path (str): Path to the zarrfile
        key (str): internal key of the desired dataset
        slices (Optional[slice], optional): Optional, slice to load. Defaults to None.
        info_only (bool, optional): if true will return a tuple with infos such as voxel resolution, units and shape. \
        Defaults to False.

    Returns:
        Union[tuple, tuple[np.array, tuple]]: dataset as numpy array and infos
    """
    with zarr.open(path, 'r') as f:
        if key is None:
            key = _find_input_key(f)

        voxel_size = read_zarr_voxel_size(f, key)
        file_shape = f[key].shape

        infos = (voxel_size, file_shape, key, 'um')
        if info_only:
            return infos

        file = f[key][...] if slices is None else f[key][slices]

    return file, infos


def create_zarr(path: str,
                stack: np.ndarray,
                key: str,
                voxel_size: tuple[float, float, float] = (1.0, 1.0, 1.0),
                mode: str = 'a') -> None:
    """
    Helper function to create a dataset inside a zarr file
    Args:
        path (str): file path
        stack (np.array): numpy array to save as dataset in the zarr file
        key (str): key of the dataset in the zarr file
        voxel_size (tuple[float, float, float]: voxel size in micrometers
        mode (str): mode to open the zarr file ['w', 'a']

    Returns:
        None
    """

    with zarr.open(path, mode) as f:
        f.create_dataset(key, data=stack, compression='gzip', overwrite=True)
        # save voxel_size
        f[key].attrs['element_size_um'] = voxel_size


def list_keys(path):
    """
    List all keys in a zarr file
    Args:
        path: path to the zarr file

    Returns:
        list of keys
    """
    def _recursive_find_keys(f, base: Path = Path('/')):
        _list_keys = []
        for key, dataset in f.items():
            if isinstance(dataset, zarr.Group):
                new_base = base / key
                _list_keys += _recursive_find_keys(dataset, new_base)

            elif isinstance(dataset, zarr.Array):
                new_key = str(base / key)
                _list_keys.append(new_key)
        return _list_keys

    with zarr.open(path, 'r') as zarr_f:
        return _recursive_find_keys(zarr_f)


def del_zarr_key(path: str, key: str, mode: str = 'a') -> None:
    """
    helper function to delete a dataset from a zarrfile
    """
    with zarr.open(path, mode) as f:
        if key in f:
            del f[key]


def rename_zarr_key(path: str, old_key: str, new_key: str, mode='r+') -> None:
    """ Rename the 'old_key' dataset to 'new_key' """
    with zarr.open(path, mode) as f:
        if old_key in f:
            f[new_key] = f[old_key]
            del f[old_key]
