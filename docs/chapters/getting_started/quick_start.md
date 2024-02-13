# Quick Start
There are three ways to use PlantSeg:
* [Napari viewer](https://hci-unihd.github.io/plant-seg/chapters/plantseg_interactive_napari/) This is the most interactive way to use PlantSeg. It allows to run all the steps of the pipeline and visualize the results in a single using the [napari](https://napari.org/stable/) viewer. This is the recommended way to use PlantSeg on new data.
* [Classic GUI](https://hci-unihd.github.io/plant-seg/chapters/plantseg_classic_gui/) This is the easiest way to use PlantSeg on large batches of data. It allows to configure and run all the steps of the pipeline. It is recommended to use this mode for high throughput processing and for running PlantSeg on a local machine.
* [Command line](https://hci-unihd.github.io/plant-seg/chapters/plantseg_classic_cli/) This modality of using PlantSeg is particularly suited for high throughput processing and for running PlantSeg on a remote server. It allows to configure and run the pipeline using a configuration file.

## Quick start using the Napari viewer
First, activate the newly created conda environment with:
```bash
conda activate plant-seg
```
then, start the plantseg in napari
```bash
$ plantseg --napari
```

## Quick start using the Classic GUI
First, activate the newly created conda environment with:
```bash
conda activate plant-seg
```

then, run the GUI by simply typing:
```bash
$ plantseg --gui
```

## Quick start using the Command line
First, activate the newly created conda environment with:
```bash
conda activate plant-seg
```
then, one can just start the pipeline with
```bash
plantseg --config CONFIG_PATH
```
where `CONFIG_PATH` is the path to the YAML configuration file. See [config.yaml](examples/config.yaml) for a sample configuration file.