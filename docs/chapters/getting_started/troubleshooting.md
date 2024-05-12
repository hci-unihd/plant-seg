# Troubleshooting <!-- omit in toc -->

This section provides solutions to common issues you might encounter while using PlantSeg. Click on a problem to jump to its specific solution.

* [Problems with `--headless` and `dask[distributed]`](#problems-with---headless-and-daskdistributed)
* [Could not load library `libcudnn_ops_infer.so.8`](#could-not-load-library-libcudnn_ops_inferso8)
* [Missing configuration key errors](#missing-configuration-key-errors)
* [Cannot import `lifted_problem_from_probabilities`](#cannot-import-lifted_problem_from_probabilities)
* [Other issues](#other-issues)

----

## Problems with `--headless` and `dask[distributed]`

If you encounter the following error:

```plaintext
ImportError: dask.distributed is not installed.
```

Please install `dask[distributed]` to enable headless mode in PlantSeg. Run the following commands in your terminal:

```bash
mamba activate plant-seg
mamba install -c pytorch -c nvidia -c conda-forge dask distributed
```

## Could not load library `libcudnn_ops_infer.so.8`

If you encounter this error:

```plaintext
Could not load library libcudnn_ops_infer.so.8. Error: libcudnn_ops_infer.so.8: cannot open shared object file: No such file or directory
```

Resolve this by installing `cudnn` using the following command:

```bash
mamba install -c conda-forge cudnn
```

----

## Missing configuration key errors

If you encounter a `RuntimeError` about a missing key, such as:

```plaintext
RuntimeError: key : 'crop_volume' is missing, plant-seg requires 'crop_volume' to run
```

This usually means the session configuration file is corrupted or outdated. To fix this:

```bash
rm ~/.plantseg_models/configs/config_gui_last.yaml
```

Ensure your configuration file is properly formatted and includes all required keys. Example configurations can be found in the `examples` directory of this repository.

----

## Cannot import `lifted_problem_from_probabilities`

If you receive an error related to importing from `elf.segmentation.features`, reinstall [elf](https://github.com/constantinpape/elf):

```bash
conda install -c conda-forge python-elf
```

----

## Other issues

PlantSeg is actively developed, and sometimes model or configuration files saved in `~/.plantseg_models` may become outdated. If you encounter errors related to configuration loading:

1. Close the PlantSeg application.
2. Delete the `~/.plantsep_models` directory.
3. Restart the application and try again.

These steps should help resolve any issues and enhance your experience with PlantSeg.
