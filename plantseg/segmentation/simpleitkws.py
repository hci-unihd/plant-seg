import numpy as np

import SimpleITK as sitk
from plantseg.pipeline.steps import AbstractSegmentationStep


class SimpleITKWatershed(AbstractSegmentationStep):
    def __init__(self,
                 predictions_paths,
                 save_directory="ITKWatershed",
                 ws_2D=True,
                 ws_threshold=0.4,
                 ws_minsize=50,
                 ws_sigma=0.3,
                 n_threads=8,
                 state=True,
                 **kwargs):

        super().__init__(input_paths=predictions_paths,
                         save_directory=save_directory,
                         file_suffix='_itkws',
                         state=state)

        self.ws_threshold = ws_threshold
        self.ws_minsize = ws_minsize
        self.ws_sigma = ws_sigma

    def process(self, pmaps):
        # Itk gaussian smoothing
        itk_pmaps = sitk.GetImageFromArray(pmaps)
        if self.ws_sigma > 0:
            itk_pmaps = sitk.SmoothingRecursiveGaussian(itk_pmaps, self.ws_sigma)

        # Itk watershed + size filtering
        itk_segmentation = sitk.MorphologicalWatershed(itk_pmaps,
                                                       self.ws_threshold,
                                                       markWatershedLine=False,
                                                       fullyConnected=False)
        itk_segmentation = sitk.RelabelComponent(itk_segmentation, self.ws_minsize)

        return sitk.GetArrayFromImage(itk_segmentation).astype(np.uint16)