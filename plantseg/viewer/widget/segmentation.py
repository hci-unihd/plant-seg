from concurrent.futures import Future
from typing import Callable, Optional

from magicgui import magicgui
from napari import Viewer
from napari.layers import Labels, Image, Layer
from napari.types import LayerDataTuple

from plantseg.dataprocessing.functional.advanced_dataprocessing import fix_over_under_segmentation_from_nuclei
from plantseg.dataprocessing.functional.advanced_dataprocessing import remove_false_positives_by_foreground_probability
from plantseg.dataprocessing.functional.dataprocessing import normalize_01
from plantseg.segmentation.functional import gasp, multicut, dt_watershed, mutex_ws
from plantseg.segmentation.functional import lifted_multicut_from_nuclei_segmentation, lifted_multicut_from_nuclei_pmaps
from plantseg.viewer.logging import napari_formatted_logging
from plantseg.viewer.widget.proofreading.proofreading import widget_split_and_merge_from_scribbles
from plantseg.viewer.widget.utils import start_threading_process, create_layer_name, layer_properties

STACKED = [('2D', True), ('3D', False)]


def _pmap_warn(thread: str):
    napari_formatted_logging(
        'Pmap/Image layer appears to be a raw image and not a pmap. For the best segmentation results, '
        'try to use a boundaries probability layer (e.g. from the Run Prediction widget)',
        thread=thread,
        level='warning',
    )


def _generic_clustering(
    image: Image,
    labels: Labels,
    beta: float = 0.5,
    minsize: int = 100,
    name: str = 'GASP',
    agg_func: Callable = gasp,
    viewer: Optional[Viewer] = None,
) -> Future[LayerDataTuple]:
    if 'pmap' not in image.metadata:
        _pmap_warn(f'{name} Clustering Widget')

    out_name = create_layer_name(image.name, name)
    inputs_names = (image.name, labels.name)
    layer_kwargs = layer_properties(name=out_name, scale=image.scale, metadata=image.metadata)
    layer_type = 'labels'
    step_kwargs = dict(beta=beta, post_minsize=minsize)

    return start_threading_process(
        agg_func,
        runtime_kwargs={'boundary_pmaps': image.data, 'superpixels': labels.data},
        statics_kwargs=step_kwargs,
        out_name=out_name,
        input_keys=inputs_names,
        layer_kwarg=layer_kwargs,
        layer_type=layer_type,
        step_name=f'{name} Clustering',
        viewer=viewer,
        widgets_to_update=[widget_split_and_merge_from_scribbles.segmentation],
    )


@magicgui(
    call_button='Run Clustering',
    image={
        'label': 'Pmap/Image',
        'tooltip': 'Raw or boundary image to use as input for clustering.',
    },
    _labels={
        'label': 'Over-segmentation',
        'tooltip': 'Over-segmentation labels layer to use as input for clustering.',
    },
    mode={
        'label': 'Aggl. Mode',
        'choices': ['GASP', 'MutexWS', 'MultiCut'],
        'tooltip': 'Select which agglomeration algorithm to use.',
    },
    beta={
        'label': 'Under/Over segmentation factor',
        'tooltip': 'A low value will increase under-segmentation tendency '
        'and a large value increase over-segmentation tendency.',
        'widget_type': 'FloatSlider',
        'max': 1.0,
        'min': 0.0,
    },
    minsize={
        'label': 'Min-size',
        'tooltip': 'Minimum segment size allowed in voxels.',
    },
)
def widget_agglomeration(
    viewer: Viewer,
    image: Image,
    _labels: Labels,
    mode: str = "GASP",
    beta: float = 0.6,
    minsize: int = 100,
) -> Future[LayerDataTuple]:
    if mode == 'GASP':
        func = gasp

    elif mode == 'MutexWS':
        func = mutex_ws

    else:
        func = multicut

    return _generic_clustering(image, _labels, beta=beta, minsize=minsize, name=mode, agg_func=func, viewer=viewer)


@magicgui(
    call_button='Run Lifted MultiCut',
    image={
        'label': 'Pmap/Image',
        'tooltip': 'Raw or boundary image to use as input for clustering.',
    },
    nuclei={
        'label': 'Nuclei',
        'tooltip': 'Nuclei binary predictions or Nuclei segmentation.',
    },
    _labels={
        'label': 'Over-segmentation',
        'tooltip': 'Over-segmentation labels layer to use as input for clustering.',
    },
    beta={
        'label': 'Under/Over segmentation factor',
        'tooltip': 'A low value will increase under-segmentation tendency '
        'and a large value increase over-segmentation tendency.',
        'widget_type': 'FloatSlider',
        'max': 1.0,
        'min': 0.0,
    },
    minsize={
        'label': 'Min-size',
        'tooltip': 'Minimum segment size allowed in voxels.',
    },
)
def widget_lifted_multicut(
    image: Image, nuclei: Layer, _labels: Labels, beta: float = 0.5, minsize: int = 100
) -> Future[LayerDataTuple]:
    if 'pmap' not in image.metadata:
        _pmap_warn('Lifted MultiCut Widget')

    if isinstance(nuclei, Image):
        lmc = lifted_multicut_from_nuclei_pmaps
        extra_key = 'nuclei_pmaps'
    elif isinstance(nuclei, Labels):
        lmc = lifted_multicut_from_nuclei_segmentation
        extra_key = 'nuclei_seg'
    else:
        raise ValueError(f'{nuclei} must be either an image or a labels layer')

    out_name = create_layer_name(image.name, 'LiftedMultiCut')
    inputs_names = (image.name, nuclei.name, _labels.name)
    layer_kwargs = layer_properties(name=out_name, scale=image.scale, metadata=image.metadata)
    layer_type = 'labels'
    step_kwargs = dict(beta=beta, post_minsize=minsize)

    return start_threading_process(
        lmc,
        runtime_kwargs={'boundary_pmaps': image.data, extra_key: nuclei.data, 'superpixels': _labels.data},
        statics_kwargs=step_kwargs,
        out_name=out_name,
        input_keys=inputs_names,
        layer_kwarg=layer_kwargs,
        layer_type=layer_type,
        step_name='Lifted Multicut Clustering',
    )


def dtws_wrapper(
    boundary_pmaps,
    stacked: bool = True,
    threshold: float = 0.5,
    min_size: int = 100,
    sigma_seeds: float = 0.2,
    sigma_weights: float = 2.0,
    alpha: float = 1.0,
    pixel_pitch: tuple[int, int, int] = (1, 1, 1),
    apply_nonmax_suppression: bool = False,
    nuclei: bool = False,
):
    if nuclei:
        boundary_pmaps = normalize_01(boundary_pmaps)
        boundary_pmaps = 1.0 - boundary_pmaps
        mask = boundary_pmaps < threshold
    else:
        mask = None

    return dt_watershed(
        boundary_pmaps=boundary_pmaps,
        threshold=threshold,
        min_size=min_size,
        stacked=stacked,
        sigma_seeds=sigma_seeds,
        sigma_weights=sigma_weights,
        alpha=alpha,
        pixel_pitch=pixel_pitch,
        apply_nonmax_suppression=apply_nonmax_suppression,
        mask=mask,
    )


@magicgui(
    call_button='Run Watershed',
    image={
        'label': 'Pmap/Image',
        'tooltip': 'Raw or boundary image to use as input for Watershed.',
    },
    stacked={
        'label': 'Stacked',
        'tooltip': 'Define if the Watershed will run slice by slice (faster) ' 'or on the full volume (slower).',
        'widget_type': 'RadioButtons',
        'orientation': 'horizontal',
        'choices': STACKED,
    },
    threshold={
        'label': 'Threshold',
        'tooltip': 'A low value will increase over-segmentation tendency '
        'and a large value increase under-segmentation tendency.',
        'widget_type': 'FloatSlider',
        'max': 1.0,
        'min': 0.0,
    },
    min_size={
        'label': 'Min-size',
        'tooltip': 'Minimum segment size allowed in voxels.',
    },
    # Advanced parameters
    show_advanced={
        'label': 'Show Advanced Parameters',
        'tooltip': 'Show advanced parameters for the Watershed algorithm.',
        'widget_type': 'CheckBox',
    },
    sigma_seeds={'label': 'Sigma seeds'},
    sigma_weights={'label': 'Sigma weights'},
    alpha={'label': 'Alpha'},
    use_pixel_pitch={'label': 'Use pixel pitch'},
    pixel_pitch={'label': 'Pixel pitch'},
    apply_nonmax_suppression={'label': 'Apply nonmax suppression'},
    nuclei={'label': 'Is image Nuclei'},
)
def widget_dt_ws(
    image: Image,
    stacked: bool = False,
    threshold: float = 0.5,
    min_size: int = 100,
    show_advanced: bool = False,
    sigma_seeds: float = 0.2,
    sigma_weights: float = 2.0,
    alpha: float = 1.0,
    use_pixel_pitch: bool = False,
    pixel_pitch: tuple[int, int, int] = (1, 1, 1),
    apply_nonmax_suppression: bool = False,
    nuclei: bool = False,
) -> Future[LayerDataTuple]:
    if 'pmap' not in image.metadata:
        _pmap_warn("Watershed Widget")

    out_name = create_layer_name(image.name, 'dtWS')
    inputs_names = (image.name,)
    layer_kwargs = layer_properties(name=out_name, scale=image.scale, metadata=image.metadata)
    layer_type = 'labels'

    step_kwargs = {
        'threshold': threshold,
        'min_size': min_size,
        'stacked': stacked,
        'sigma_seeds': sigma_seeds,
        'sigma_weights': sigma_weights,
        'alpha': alpha,
        'pixel_pitch': pixel_pitch if use_pixel_pitch else None,
        'apply_nonmax_suppression': apply_nonmax_suppression,
        'nuclei': nuclei,
    }

    return start_threading_process(
        dtws_wrapper,
        runtime_kwargs={'boundary_pmaps': image.data},
        statics_kwargs=step_kwargs,
        out_name=out_name,
        input_keys=inputs_names,
        layer_kwarg=layer_kwargs,
        layer_type=layer_type,
        step_name='Watershed Segmentation',
    )


widget_dt_ws.sigma_seeds.hide()
widget_dt_ws.sigma_weights.hide()
widget_dt_ws.alpha.hide()
widget_dt_ws.use_pixel_pitch.hide()
widget_dt_ws.pixel_pitch.hide()
widget_dt_ws.apply_nonmax_suppression.hide()
widget_dt_ws.nuclei.hide()


@widget_dt_ws.show_advanced.changed.connect
def _on_show_advanced_changed(state: bool):
    if state:
        widget_dt_ws.sigma_seeds.show()
        widget_dt_ws.sigma_weights.show()
        widget_dt_ws.alpha.show()
        widget_dt_ws.use_pixel_pitch.show()
        widget_dt_ws.pixel_pitch.show()
        widget_dt_ws.apply_nonmax_suppression.show()
        widget_dt_ws.nuclei.show()
    else:
        widget_dt_ws.sigma_seeds.hide()
        widget_dt_ws.sigma_weights.hide()
        widget_dt_ws.alpha.hide()
        widget_dt_ws.use_pixel_pitch.hide()
        widget_dt_ws.pixel_pitch.hide()
        widget_dt_ws.apply_nonmax_suppression.hide()
        widget_dt_ws.nuclei.hide()


@magicgui(
    call_button='Run Watershed',
    image={
        'label': 'Pmap/Image',
        'tooltip': 'Raw or boundary image to use as input for Watershed.',
    },
    stacked={
        'label': 'Stacked',
        'tooltip': 'Define if the Watershed will run slice by slice (faster) ' 'or on the full volume (slower).',
        'widget_type': 'RadioButtons',
        'orientation': 'horizontal',
        'choices': STACKED,
    },
    threshold={
        'label': 'Threshold',
        'tooltip': 'A low value will increase over-segmentation tendency '
        'and a large value increase under-segmentation tendency.',
        'widget_type': 'FloatSlider',
        'max': 1.0,
        'min': 0.0,
    },
    min_size={
        'label': 'Min-size',
        'tooltip': 'Minimum segment size allowed in voxels.',
    },
)
def widget_simple_dt_ws(
    image: Image,
    stacked: bool = False,
    threshold: float = 0.5,
    min_size: int = 100,
) -> Future[LayerDataTuple]:
    if 'pmap' not in image.metadata:
        _pmap_warn("Watershed Widget")

    out_name = create_layer_name(image.name, 'dtWS')
    inputs_names = (image.name,)
    layer_kwargs = layer_properties(name=out_name, scale=image.scale, metadata=image.metadata)
    layer_type = 'labels'

    step_kwargs = dict(threshold=threshold, min_size=min_size, stacked=stacked, pixel_pitch=None)

    return start_threading_process(
        dtws_wrapper,
        runtime_kwargs={'boundary_pmaps': image.data},
        statics_kwargs=step_kwargs,
        out_name=out_name,
        input_keys=inputs_names,
        layer_kwarg=layer_kwargs,
        layer_type=layer_type,
        step_name='Watershed Segmentation',
    )


@magicgui(
    call_button='Run Segmentation Fix from Nuclei',
    cell_segmentation={'label': 'Cell Segmentation'},
    nuclei_segmentation={'label': 'Nuclei Segmentation'},
    boundary_pmaps={'label': 'Boundary Pmap/Image'},
    threshold={
        'label': 'Threshold',
        'widget_type': 'FloatRangeSlider',
        'max': 100,
        'min': 0,
        'step': 0.1,
    },
    quantile={
        'label': 'Nuclei Quantile',
        'widget_type': 'FloatRangeSlider',
        'max': 100,
        'min': 0,
        'step': 0.1,
    },
)
def widget_fix_over_under_segmentation_from_nuclei(
    cell_segmentation: Labels,
    nuclei_segmentation: Labels,
    boundary_pmaps: Image,
    threshold=(33, 66),
    quantile=(0.1, 99.9),
) -> Future[LayerDataTuple]:
    out_name = create_layer_name(cell_segmentation.name, 'NucleiSegFix')
    threshold_merge, threshold_split = threshold
    threshold_merge, threshold_split = threshold_merge / 100, threshold_split / 100
    quantile = tuple([q / 100 for q in quantile])

    if boundary_pmaps is not None:
        if 'pmap' not in boundary_pmaps.metadata:
            _pmap_warn("Fix Over/Under Segmentation from Nuclei Widget")
        inputs_names = (cell_segmentation.name, nuclei_segmentation.name, boundary_pmaps.name)
        func_kwargs = {
            'cell_seg': cell_segmentation.data,
            'nuclei_seg': nuclei_segmentation.data,
            'boundary': boundary_pmaps.data,
        }
    else:
        inputs_names = (cell_segmentation.name, nuclei_segmentation.name)
        func_kwargs = {'cell_seg': cell_segmentation.data, 'nuclei_seg': nuclei_segmentation.data}

    layer_kwargs = layer_properties(name=out_name, scale=cell_segmentation.scale, metadata=cell_segmentation.metadata)
    layer_type = 'labels'
    step_kwargs = dict(threshold_merge=threshold_merge, threshold_split=threshold_split, quantiles_nuclei=quantile)

    return start_threading_process(
        fix_over_under_segmentation_from_nuclei,
        runtime_kwargs=func_kwargs,
        statics_kwargs=step_kwargs,
        out_name=out_name,
        input_keys=inputs_names,
        layer_kwarg=layer_kwargs,
        layer_type=layer_type,
        step_name='Fix Over / Under Segmentation',
    )


@magicgui(
    call_button='Run Segmentation Fix from Foreground Pmap',
    segmentation={'label': 'Segmentation'},
    foreground={'label': 'Foreground Pmap'},
    threshold={
        'label': 'Threshold',
        'widget_type': 'FloatSlider',
        'max': 1.0,
        'min': 0.0,
    },
)
def widget_fix_false_positive_from_foreground_pmap(
    segmentation: Labels, foreground: Image, threshold=0.6  # TODO: maybe also allow labels
) -> Future[LayerDataTuple]:
    out_name = create_layer_name(segmentation.name, 'FGPmapFix')

    inputs_names = (segmentation.name, foreground.name)
    func_kwargs = {'segmentation': segmentation.data, 'foreground': foreground.data}

    layer_kwargs = layer_properties(name=out_name, scale=segmentation.scale, metadata=segmentation.metadata)
    layer_type = 'labels'
    step_kwargs = dict(threshold=threshold)

    return start_threading_process(
        remove_false_positives_by_foreground_probability,
        runtime_kwargs=func_kwargs,
        statics_kwargs=step_kwargs,
        out_name=out_name,
        input_keys=inputs_names,
        layer_kwarg=layer_kwargs,
        layer_type=layer_type,
        step_name='Reduce False Positives',
    )
