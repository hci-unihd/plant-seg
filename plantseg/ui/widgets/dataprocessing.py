from concurrent.futures import Future
from enum import Enum
from typing import Tuple, Union

import numpy as np
from magicgui import magicgui
from napari import Viewer
from napari.layers import Image, Labels, Shapes, Layer
from napari.types import LayerDataTuple

from plantseg.dataprocessing.functional import image_gaussian_smoothing, image_rescale
from plantseg.dataprocessing.functional.dataprocessing import compute_scaling_factor, compute_scaling_voxelsize
from plantseg.dataprocessing.functional.labelprocessing import relabel_segmentation as _relabel_segmentation
from plantseg.dataprocessing.functional.labelprocessing import set_background_to_value
from plantseg.utils import list_models, get_model_resolution
from plantseg.ui.widgets.predictions import widget_unet_predictions
from plantseg.ui.widgets.segmentation import widget_agglomeration, widget_lifted_multicut, widget_simple_dt_ws
from plantseg.ui.widgets.utils import return_value_if_widget
from plantseg.ui.widgets.utils import start_threading_process, create_layer_name, layer_properties


@magicgui(call_button='Run Gaussian Smoothing',
          image={'label': 'Image',
                 'tooltip': 'Image layer to apply the smoothing.'},
          sigma={'label': 'Sigma',
                 'widget_type': 'FloatSlider',
                 'tooltip': 'Define the size of the gaussian smoothing kernel. '
                            'The larger the more blurred will be the output image.',
                 'max': 10.,
                 'min': 0.1})
def widget_gaussian_smoothing(viewer: Viewer,
                              image: Image,
                              sigma: float = 1.,
                              ) -> Future[LayerDataTuple]:
    out_name = create_layer_name(image.name, 'GaussianSmoothing')
    inputs_kwarg = {'image': image.data}
    step_kwargs = {'sigma': sigma}
    inputs_names = (image.name,)
    layer_kwargs = layer_properties(name=out_name, scale=image.scale, metadata=image.metadata)
    layer_type = 'image'

    return start_threading_process(image_gaussian_smoothing,
                                   runtime_kwargs=inputs_kwarg,
                                   statics_kwargs=step_kwargs,
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   layer_type=layer_type,
                                   step_name='Gaussian Smoothing',
                                   viewer=viewer,
                                   widgets_to_update=[widget_unet_predictions.image,
                                                      widget_agglomeration.image,
                                                      widget_lifted_multicut.image,
                                                      widget_simple_dt_ws.image,
                                                      widget_rescaling.image,
                                                      widget_cropping.image]
                                   )


class RescaleType(Enum):
    nearest = 0
    linear = 1
    bilinear = 2


@magicgui(call_button='Run Image Rescaling',
          image={'label': 'Image or Label',
                 'tooltip': 'Layer to apply the rescaling.'},
          rescaling_factor={'label': 'Rescaling factor',
                            'tooltip': 'Define the scaling factor to use for resizing the input image.'},
          out_voxel_size={'label': 'Out voxel size',
                          'tooltip': 'Define the output voxel size. Units are same as imported, '
                                     '(if units are missing default is "um").'},
          reference_layer={'label': 'Reference layer',
                           'tooltip': 'Rescale to same voxel size as selected layer.'},
          reference_model={'label': 'Reference model',
                           'tooltip': 'Rescale to same voxel size as selected model.',
                           'choices': list_models()},
          order={'label': 'Interpolation order',
                 'widget_type': 'ComboBox',
                 'choices': RescaleType,
                 'tooltip': '0 for nearest neighbours (default for labels), 1 for linear, 2 for bilinear.',
                 })
def widget_rescaling(viewer: Viewer,
                     image: Layer,
                     rescaling_factor: Tuple[float, float, float] = (1., 1., 1.),
                     out_voxel_size: Tuple[float, float, float] = (1., 1., 1.),
                     reference_layer: Union[None, Layer] = None,
                     reference_model: str = list_models()[0],
                     order=RescaleType.linear,
                     ) -> Future[LayerDataTuple]:
    if isinstance(image, Image):
        layer_type = 'image'
        order = order.value

    elif isinstance(image, Labels):
        layer_type = 'labels'
        order = 0

    else:
        raise ValueError(f'{type(image)} cannot be rescaled, please use Image layers or Labels layers')

    current_resolution = image.scale
    rescaling_factor = [float(x) for x in rescaling_factor]

    if image.data.ndim == 2:
        rescaling_factor[0] = 1.

    out_voxel_size = compute_scaling_voxelsize(current_resolution, scaling_factor=rescaling_factor)

    out_name = create_layer_name(image.name, 'Rescaled')
    inputs_kwarg = {'image': image.data}
    inputs_names = (image.name,)
    step_kwargs = {'factor': rescaling_factor, 'order': order}
    layer_kwargs = layer_properties(name=out_name,
                                    scale=out_voxel_size,
                                    metadata={**image.metadata,
                                              **{'original_voxel_size': current_resolution}})

    return start_threading_process(image_rescale,
                                   runtime_kwargs=inputs_kwarg,
                                   statics_kwargs=step_kwargs,
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   step_name='Rescaling',
                                   layer_type=layer_type,
                                   viewer=viewer,
                                   widgets_to_update=[widget_unet_predictions.image,
                                                      widget_agglomeration.image,
                                                      widget_lifted_multicut.image,
                                                      widget_simple_dt_ws.image,
                                                      widget_cropping.image,
                                                      widget_gaussian_smoothing.image]
                                   )


@widget_rescaling.image.changed.connect
def _on_image_changed(image: Layer):
    image = return_value_if_widget(image)
    widget_rescaling.out_voxel_size.value = image.scale


@widget_rescaling.out_voxel_size.changed.connect
def _on_voxel_size_changed(voxel_size: Tuple[float, float, float]):
    voxel_size = return_value_if_widget(voxel_size)
    rescaling_factor = compute_scaling_factor(widget_rescaling.image.value.scale, voxel_size)
    widget_rescaling.rescaling_factor.value = rescaling_factor


@widget_rescaling.reference_layer.changed.connect
def _on_reference_layer_changed(reference_layer: Layer):
    reference_layer = return_value_if_widget(reference_layer)
    rescaling_factor = compute_scaling_factor(widget_rescaling.image.value.scale, reference_layer.scale)
    widget_rescaling.rescaling_factor.value = rescaling_factor
    widget_rescaling.out_voxel_size.value = reference_layer.scale


@widget_rescaling.reference_model.changed.connect
def _on_reference_model_changed(reference_model: str):
    reference_model = return_value_if_widget(reference_model)
    out_voxel_size = get_model_resolution(reference_model)
    rescaling_factor = compute_scaling_factor(widget_rescaling.image.value.scale, out_voxel_size)
    widget_rescaling.rescaling_factor.value = rescaling_factor
    widget_rescaling.out_voxel_size.value = out_voxel_size


def _compute_slices(rectangle, crop_z, shape):
    z_start = int(crop_z[0])
    z_end = int(crop_z[1])
    z_slice = slice(z_start, z_end)

    if rectangle is None:
        return z_slice, slice(0, shape[1]), slice(0, shape[2])

    x_start = max(rectangle[0, 1], 0)
    x_end = min(rectangle[2, 1], shape[1])
    x_slice = slice(x_start, x_end)

    y_start = max(rectangle[0, 2], 0)
    y_end = min(rectangle[2, 2], shape[2])
    y_slice = slice(y_start, y_end)
    return z_slice, x_slice, y_slice


def _cropping(data, crop_slices):
    return data[crop_slices]


@magicgui(call_button='Run Cropping',
          image={'label': 'Image or Label',
                 'tooltip': 'Layer to apply the rescaling.'},
          crop_roi={'label': 'Crop ROI',
                    'tooltip': 'This must be a shape layer with a rectangle XY overlaying the area to crop.'},
          # FloatRangeSlider and RangeSlider are not working very nicely with napari, they are usable but not very
          # nice. maybe we should use a custom widgets for this.
          crop_z={'label': 'Z slices',
                  'tooltip': 'Numer of z slices to take next to the current selection.',
                  'widget_type': 'FloatRangeSlider', 'max': 100, 'min': 0, 'step': 1,
                  'readout': False,
                  'tracking': False},
          )
def widget_cropping(viewer: Viewer,
                    image: Layer,
                    crop_roi: Union[Shapes, None] = None,
                    crop_z: tuple[int, int] = (0, 100),
                    ) -> Future[LayerDataTuple]:
    if crop_roi is not None:
        assert len(crop_roi.shape_type) == 1, "Only one rectangle should be used for cropping"
        assert crop_roi.shape_type[0] == 'rectangle', "Only a rectangle shape should be used for cropping"

    if isinstance(image, Image):
        layer_type = 'image'

    elif isinstance(image, Labels):
        layer_type = 'labels'

    else:
        raise ValueError(f'{type(image)} cannot be cropped, please use Image layers or Labels layers')

    out_name = create_layer_name(image.name, 'cropped')
    inputs_names = (image.name,)
    layer_kwargs = layer_properties(name=out_name,
                                    scale=image.scale,
                                    metadata=image.metadata)

    if crop_roi is not None:
        rectangle = crop_roi.data[0].astype('int64')
    else:
        rectangle = None

    crop_slices = _compute_slices(rectangle, crop_z, image.data.shape)

    return start_threading_process(_cropping,
                                   runtime_kwargs={'data': image.data},
                                   statics_kwargs={'crop_slices': crop_slices},
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   layer_type=layer_type,
                                   step_name='Cropping',
                                   skip_dag=True,
                                   viewer=viewer,
                                   widgets_to_update=[widget_unet_predictions.image,
                                                      widget_agglomeration.image,
                                                      widget_lifted_multicut.image,
                                                      widget_simple_dt_ws.image,
                                                      widget_rescaling.image,
                                                      widget_gaussian_smoothing.image]
                                   )


@widget_cropping.image.changed.connect
def _on_image_changed(image: Layer):
    image = return_value_if_widget(image)
    image_shape = image.data.shape

    if image_shape[0] == 1:
        widget_cropping.crop_z.hide()
        return None

    widget_cropping.crop_z.show()

    widget_cropping.crop_z.max = int(image_shape[0])
    widget_cropping.crop_z.step = 1
    if widget_cropping.crop_z.value[1] > image_shape[0]:
        widget_cropping.crop_z.value[1] = int(image_shape[0])


def _two_layers_operation(data1, data2, operation, weights: float = 0.5):
    if operation == 'Mean':
        return weights * data1 + (1. - weights) * data2
    elif operation == 'Maximum':
        return np.maximum(data1, data2)
    else:
        return np.minimum(data1, data2)


@magicgui(call_button='Run Merge Layers',
          image1={'label': 'Image 1'},
          image2={'label': 'Image 2'},
          operation={'label': 'Operation',
                     'tooltip': 'Operation used to merge the two layers.',
                     'widget_type': 'RadioButtons',
                     'orientation': 'horizontal',
                     'choices': ['Mean',
                                 'Maximum',
                                 'Minimum']},
          weights={'label': 'Mean weights',
                   'widget_type': 'FloatSlider', 'max': 1., 'min': 0.},
          )
def widget_add_layers(viewer: Viewer,
                      image1: Image,
                      image2: Image,
                      operation: str = 'Maximum',
                      weights: float = 0.5,
                      ) -> Future[LayerDataTuple]:
    out_name = create_layer_name(f'{image1.name}-{image2.name}', operation)
    inputs_names = (image1.name, image2.name)
    layer_kwargs = layer_properties(name=out_name,
                                    scale=image1.scale,
                                    metadata=image1.metadata)
    layer_type = 'image'
    step_kwargs = dict(weights=weights, operation=operation)
    assert image1.data.shape == image2.data.shape

    return start_threading_process(_two_layers_operation,
                                   runtime_kwargs={'data1': image1.data, 'data2': image2.data},
                                   statics_kwargs=step_kwargs,
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   layer_type=layer_type,
                                   step_name='Merge Layers',
                                   viewer=viewer,
                                   widgets_to_update=[widget_unet_predictions.image,
                                                      widget_agglomeration.image,
                                                      widget_lifted_multicut.image,
                                                      widget_simple_dt_ws.image]
                                   )


@widget_add_layers.operation.changed.connect
def _on_operation_changed(operation: str):
    operation = return_value_if_widget(operation)
    if operation == 'Mean':
        widget_add_layers.weights.show()
    else:
        widget_add_layers.weights.hide()


def _label_processing(segmentation, set_bg_to_0, relabel_segmentation):
    if relabel_segmentation:
        segmentation = _relabel_segmentation(segmentation)

    if set_bg_to_0:
        segmentation = set_background_to_value(segmentation, value=0)

    return segmentation


@magicgui(call_button='Run Label processing',
          segmentation={'label': 'Segmentation',
                        'tooltip': 'Segmentation can be any label layer.'},
          set_bg_to_0={'label': 'Set background to 0',
                       'tooltip': 'Set the largest idx in the image to zero.'},
          relabel_segmentation={'label': 'Relabel Segmentation',
                                'tooltip': 'Relabel segmentation contiguously to avoid labels clash.'}
          )
def widget_label_processing(segmentation: Labels,
                            set_bg_to_0: bool = True,
                            relabel_segmentation: bool = True,
                            ) -> Future[LayerDataTuple]:
    if relabel_segmentation and 'bboxes' in segmentation.metadata.keys():
        del segmentation.metadata['bboxes']

    out_name = create_layer_name(segmentation.name, 'Processed')
    inputs_kwarg = {'segmentation': segmentation.data}
    inputs_names = (segmentation.name,)
    layer_kwargs = layer_properties(name=out_name,
                                    scale=segmentation.scale,
                                    metadata=segmentation.metadata)
    layer_type = 'labels'
    step_kwargs = dict(set_bg_to_0=set_bg_to_0, relabel_segmentation=relabel_segmentation)

    return start_threading_process(_label_processing,
                                   runtime_kwargs=inputs_kwarg,
                                   statics_kwargs=step_kwargs,
                                   out_name=out_name,
                                   input_keys=inputs_names,
                                   layer_kwarg=layer_kwargs,
                                   layer_type=layer_type,
                                   step_name='Label Processing',
                                   )
