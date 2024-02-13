# PlantSeg Interactive - Napari
The PlantSeg interactive mode is the most interactive way to use PlantSeg. It allows to run all the steps of the pipeline and visualize the results interactively using the [napari](https://napari.org/stable/) viewer. This is the recommended way to use PlantSeg on new data.

## Overview
In the Napari viewer, the PlantSeg pipeline is divided into 5 main tabs:
1. **Input/Output**: This tab allows to load the input data and to save the results. Moreover contains a simple proofreading tool.
2. **DataProcessing**: This tab allows to preprocess any layer of the input data. Contains all the standard preprocessing steps of PlantSeg, plus some additional steps such as cropping and merging layers.
A detailed description of all the widgets in this tab can be found [here](https://hci-unihd.github.io/plant-seg/chapters/plantseg_interactive_napari/data_processing.md).
3. **PlantSeg Main Workflow**: This tab contains the main PlantSeg pipeline. It allows to run the complete pipeline or to run any of the steps singularly.
A detailed description of all the widgets in this tab can be found [here](https://hci-unihd.github.io/plant-seg/chapters/plantseg_interactive_napari/unet_gasp_workflow.md).
4. **Extra Segmentation**: This tab contains additional segmentation algorithms that can be used in addition to the main pipeline.
A detailed description of all the widgets in this tab can be found [here](https://hci-unihd.github.io/plant-seg/chapters/plantseg_interactive_napari/extra_seg.md).
5. **Extra Predictions**: This tab contains a widget to add addiotional trained models to PlantSeg, and some experimental CNN predictions steps.
A detailed description of all the widgets in this tab can be found [here](https://hci-unihd.github.io/plant-seg/chapters/plantseg_interactive_napari/extra_pred.md).

## Quick start using the Napari viewer 
First, activate the newly created conda environment with:
```bash
conda activate plant-seg
```
then, start the plantseg in napari
```bash
$ plantseg --napari
```
![alt text](https://github.com/hci-unihd/plant-seg/raw/assets/images/plantseg_napari.png)

## Input/Output


## Proofreading



