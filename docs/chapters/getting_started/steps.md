# PlantSeg Pipeline Overview
PlantSeg in a pipeline for 3D cell segmentation. At its core, PlantSeg implements a simple three-step pipeline:
A pre-processing step, a CNN prediction step, and a segmentation step.

## Pre-Processing
The pre-processing step is used to prepare the input data for the CNN. There are two main operations that can be performed in the pre-processing step. The first is rescaling the input data to match the resolution of the data used for training the neural network. The second is filtering the input data to remove noise.

## CNN Prediction
The CNN prediction step uses a UNet architecture to predict boundaries. The UNet architecture is a popular architecture for image segmentation tasks. The UNet architecture is a fully convolutional network that is trained to predict boundaries. The UNet architecture is trained on a large dataset of images with known boundaries. The UNet architecture is trained to predict boundaries by minimizing the difference between the predicted boundaries and the true boundaries.

## Segmentation
The segmentation step implements powerful graph partitioning techniques to obtain a segmentation from the
input stacks. If the predicted boundaries are not satisfactory, a raw image could be used (especially if the cell boundaries are very sharp, and the noise is low) but this usually does not yield satisfactory results.

The **Algorithm** menu can be used to choose the segmentation algorithm. Available choices are:
1. GASP (average): is a generalization of the classical hierarchical clustering. It usually delivers very
reliable and accurate segmentation. It is the default in PlantSeg.
2. MutexWS: Mutex Watershed is a derivative of the standard Watershed, where we do not need seeds for the
    segmentation. This algorithm performs very well in certain types of complex morphology (like )
3. MultiCut: in contrast to the other algorithms is not based on a greedy agglomeration but tries to find the
optimal global segmentation. This is, in practice, very hard, and it can be infeasible for huge stacks.
4. DtWatershed: is our implementation of the distance transform Watershed. From the input, we extract a distance map
from the boundaries. Based this distance map, seeds are placed at local minima. Then those seeds are used for
computing the Watershed segmentation. To speed up the computation of GASP, MutexWS, and MultiCut, an over-segmentation is obtained using Dt Watershed.
5. Lifted Multicut: This method is based on the Multicut algorithm, but it uses a lifted edges to include addional priors from nuclei.
