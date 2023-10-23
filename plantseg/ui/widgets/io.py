from pathlib import Path
from typing import List, Tuple
from warnings import warn

import numpy as np
from magicgui import magicgui
from napari.layers import Layer, Image, Labels
from napari.types import LayerDataTuple

from plantseg.dataprocessing.functional.dataprocessing import fix_input_shape, normalize_01
from plantseg.dataprocessing.functional.dataprocessing import image_rescale, compute_scaling_factor
from plantseg.io import H5_EXTENSIONS, TIFF_EXTENSIONS, PIL_EXTENSIONS, allowed_data_format, ZARR_EXTENSIONS
from plantseg.io import create_h5, create_tiff, create_zarr
from plantseg.io import load_tiff, load_h5, load_pill, load_zarr
from plantseg.io.h5 import list_keys as list_h5_keys
from plantseg.io.zarr import list_keys as list_zarr_keys
from plantseg.ui.dag_handler import dag_manager
from plantseg.ui.logging import napari_formatted_logging
from plantseg.ui.widgets.utils import layer_properties, return_value_if_widget


def _check_layout_string(layout):
    n_c = 0
    for l in layout:
        if l not in ['x', 'c']:
            raise ValueError(f'letter {l} found in layout [{layout}], layout should contain only x and a single c')
        if l == 'c':
            n_c += 1

    if n_c != 1:
        raise ValueError(f'letter c found in layout {n_c} times, but should be present only once')


def _filter_channel(data, channel, layout):
    slices = []
    for i, l in enumerate(layout):
        if l == 'x':
            slices.append(slice(None, None))
        else:
            if channel > data.shape[i]:
                raise ValueError(f'image has only {data.shape[i]} channels along {layout}')
            slices.append(slice(channel, channel + 1))

    return np.squeeze(data[tuple(slices)])


def napari_image_load(path, key, channel, advanced_load=False, layer_type='image'):
    path = Path(path)
    base, ext = path.stem, path.suffix
    if ext not in allowed_data_format:
        raise ValueError(f'File extension is {ext} but should be one of {allowed_data_format}')

    if ext in H5_EXTENSIONS:
        key = key if advanced_load else None
        data, (voxel_size, _, _, voxel_size_unit) = load_h5(path, key=key)

    elif ext in TIFF_EXTENSIONS:
        channel, layout = channel
        data, (voxel_size, _, _, voxel_size_unit) = load_tiff(path)
        if advanced_load:
            assert data.ndim == len(layout)
            _check_layout_string(layout)
            data = _filter_channel(data, channel=channel, layout=layout)

    elif ext in PIL_EXTENSIONS:
        data, (voxel_size, _, _, voxel_size_unit) = load_pill(path)

    elif ext in ZARR_EXTENSIONS:
        data, (voxel_size, _, _, voxel_size_unit) = load_zarr(path, key=key)

    else:
        raise NotImplementedError()

    data = fix_input_shape(data)

    if layer_type == 'image':
        data = normalize_01(data)

    elif layer_type == 'labels':
        data = data.astype('uint16')

    return {'data': data,
            'voxel_size': voxel_size,
            'voxel_size_unit': voxel_size_unit
            }


def unpack_load(loaded_dict, key):
    return loaded_dict.get(key)


@magicgui(
    call_button='Open file',
    path={'label': 'Pick a file (tiff, h5, png, jpg)',
          'mode': 'r',
          'tooltip': 'Select a file to be imported, the file can be a tiff, h5, png, jpg.'},
    path_mode={'label': 'File type',
               'choices': ['tiff, h5', 'zarr'],
               'widget_type': 'RadioButtons',
               'orientation': 'horizontal'},
    new_layer_name={'label': 'Layer Name',
                    'tooltip': 'Define the name of the output layer, default is either image or label.'},
    layer_type={
        'label': 'Layer type',
        'tooltip': 'Select if the image is a normal image or a segmentation',
        'widget_type': 'RadioButtons',
        'orientation': 'horizontal',
        'choices': ['image', 'labels']},
    advanced_load={'label': 'Advanced load a specific h5-key / tiff-channel',
                   'tooltip': 'If specified allows to select specific h5 dataset in a file,'
                              ' or specific channels in a tiff.'},
    key={'label': 'Key (h5/zarr only)',
         'choices': [''],
         'tooltip': 'Key to be loaded from h5'},
    channel={'label': 'Channel/layout (tiff only)',
             'tooltip': 'Channel to select and channels layout'})
def open_file(path: Path = Path.home(),
              path_mode: str = 'tiff, h5',
              layer_type: str = 'image',
              new_layer_name: str = '',
              advanced_load: bool = False,
              key: str = '',
              channel: Tuple[int, str] = (0, 'xcxx'),
              ) -> LayerDataTuple:
    """Open a file and return a napari layer."""
    new_layer_name = layer_type if new_layer_name == '' else new_layer_name
    loaded_dict_name = f'{new_layer_name}_loaded_dict'

    # wrap load routine and add it to the dag
    step_params = {'key': key,
                   'channel': channel,
                   'advanced_load': advanced_load,
                   'layer_type': layer_type}

    dag_manager.add_step(napari_image_load,
                         input_keys=(f'{new_layer_name}_path',),
                         output_key=loaded_dict_name,
                         step_name='Load stack',
                         static_params=step_params)

    # locally unwrap the result
    load_dict = napari_image_load(path, **step_params)
    data = load_dict['data']
    voxel_size = load_dict['voxel_size']
    voxel_size_unit = load_dict['voxel_size_unit']

    # add the key unwrapping to the dag
    for key, out_name in [('data', new_layer_name),
                          ('voxel_size', f'{new_layer_name}_voxel_size'),
                          ('voxel_size_unit', f'{new_layer_name}_voxel_size_unit')]:
        step_params = {'key': key}
        dag_manager.add_step(unpack_load,
                             input_keys=(loaded_dict_name,),
                             output_key=out_name,
                             step_name=f'Unpack {key}',
                             static_params=step_params
                             )

    # return layer

    napari_formatted_logging(f'{new_layer_name} Correctly imported, voxel_size: {voxel_size} {voxel_size_unit}',
                             thread='Open file')
    layer_kwargs = layer_properties(name=new_layer_name,
                                    scale=voxel_size,
                                    metadata={'original_voxel_size': voxel_size,
                                              'voxel_size_unit': voxel_size_unit,
                                              'root_name': new_layer_name})
    return data, layer_kwargs, layer_type


open_file.key.hide()
open_file.channel.hide()


@open_file.path_mode.changed.connect
def _on_path_mode_changed(path_mode: str):
    path_mode = return_value_if_widget(path_mode)
    if path_mode == 'tiff, h5':
        open_file.path.mode = 'r'
        open_file.path.label = 'Pick a file (.tiff, .h5, .png, .jpg)'
    elif path_mode == 'zarr':
        open_file.path.mode = 'd'
        open_file.path.label = 'Pick a folder (.zarr)'


@open_file.path.changed.connect
def _on_path_changed(path: Path):
    path = return_value_if_widget(path)
    open_file.new_layer_name.value = path.stem
    ext = path.suffix

    if ext in H5_EXTENSIONS:
        keys = list_h5_keys(path)
        open_file.key.choices = keys
        open_file.key.value = keys[0]

    elif ext in ZARR_EXTENSIONS:
        keys = list_zarr_keys(path)
        open_file.key.choices = keys
        open_file.key.value = keys[0]


@open_file.advanced_load.changed.connect
def _on_advanced_load_changed(advanced_load: bool):
    advanced_load = return_value_if_widget(advanced_load)
    if advanced_load:
        open_file.key.show()
        open_file.channel.show()

        ext = open_file.path.value.suffix
        if ext in H5_EXTENSIONS:
            keys = list_h5_keys(open_file.path.value)
            open_file.key.choices = keys
            open_file.key.value = keys[0]
        elif ext in ZARR_EXTENSIONS:
            keys = list_zarr_keys(open_file.path.value)
            open_file.key.choices = keys
            open_file.key.value = keys[0]
    else:
        open_file.key.hide()
        open_file.channel.hide()


@open_file.call_button.clicked.connect
def _on_call_button_clicked():
    open_file.advanced_load.value = False


def export_stack_as_tiff(data,
                         name,
                         directory,
                         voxel_size,
                         voxel_size_unit,
                         custom_name,
                         standard_suffix,
                         scaling_factor,
                         order,
                         stack_type,
                         dtype):
    if scaling_factor is not None:
        data = image_rescale(data, factor=scaling_factor, order=order)

    stack_name = f'{name}_{standard_suffix}' if custom_name is None else f'{name}_{custom_name}'

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    out_path = directory / f'{stack_name}.tiff'
    data = fix_input_shape(data)
    data = safe_typecast(data, dtype, stack_type)
    create_tiff(path=out_path, stack=data[...], voxel_size=voxel_size, voxel_size_unit=voxel_size_unit)
    return out_path


def export_stack_as_h5(data,
                       name,
                       directory,
                       voxel_size,
                       voxel_size_unit,
                       custom_name,
                       standard_suffix,
                       scaling_factor,
                       order,
                       stack_type,
                       dtype):
    if scaling_factor is not None:
        data = image_rescale(data, factor=scaling_factor, order=order)

    key = f'export_{standard_suffix}' if custom_name is None else custom_name

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    out_path = directory / f'{name}.h5'
    data = fix_input_shape(data)
    data = safe_typecast(data, dtype, stack_type)
    create_h5(path=out_path, stack=data[...], key=key, voxel_size=voxel_size)
    return out_path


def export_stack_as_zarr(data,
                         name,
                         directory,
                         voxel_size,
                         voxel_size_unit,
                         custom_name,
                         standard_suffix,
                         scaling_factor,
                         order,
                         stack_type,
                         dtype):
    if scaling_factor is not None:
        data = image_rescale(data, factor=scaling_factor, order=order)

    key = f'export_{standard_suffix}' if custom_name is None else custom_name

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    out_path = directory / f'{name}.zarr'
    data = fix_input_shape(data)
    data = safe_typecast(data, dtype, stack_type)
    create_zarr(path=out_path, stack=data[...], key=key, voxel_size=voxel_size)
    return out_path


def _image_typecast(data, dtype):
    data = normalize_01(data)
    if dtype != 'float32':
        data = (data * np.iinfo(dtype).max)

    data = data.astype(dtype)
    return data


def _label_typecast(data, dtype):
    return data.astype(dtype)


def safe_typecast(data, dtype, stack_type):
    if stack_type == 'image':
        return _image_typecast(data, dtype)
    elif stack_type == 'labels':
        return _label_typecast(data, dtype)
    else:
        raise NotImplementedError


def checkout(*args):
    for stack in args:
        stack = Path(stack)
        assert stack.is_file()


@magicgui(
    call_button='Export stack',
    images={'label': 'Layers to export',
            'layout': 'vertical',
            'tooltip': 'Select all layer to be exported, and (optional) set a custom file name suffix that will be '
                       'appended at end of the layer name.'},
    data_type={'label': 'Data Type',
               'choices': ['float32', 'uint8', 'uint16'],
               'tooltip': 'Export datatype (uint16 for segmentation) and all others for images.'},
    export_format={'label': 'Export format',
                   'choices': ['tiff', 'h5', 'zarr'],
                   'tooltip': 'Export format, if tiff is selected, each layer will be exported as a separate file. '
                              'If h5 is selected, all layers will be exported in a single file.'},
    directory={'label': 'Directory to export files',
               'mode': 'd',
               'tooltip': 'Select the directory where the files will be exported'},
    workflow_name={'label': 'Workflow name',
                   'tooltip': 'Name of the workflow object.'},
)
def export_stacks(images: List[Tuple[Layer, str]],
                  directory: Path = Path.home(),
                  export_format: str = 'tiff',
                  rescale_to_original_resolution: bool = True,
                  data_type: str = 'float32',
                  workflow_name: str = 'workflow',
                  ) -> None:
    export_name = []

    for i, (image, image_custom_name) in enumerate(images):
        # parse and check input to the function
        if isinstance(image, Image):
            order = 1
            stack_type = 'image'
            dtype = data_type

        elif isinstance(image, Labels):
            order = 0

            stack_type = 'labels'
            dtype = 'uint16'
            if data_type != 'uint16':
                warn(f"{data_type} is not a valid type for Labels, please use uint8 or uint16")
        else:
            raise ValueError(f'{type(image)} cannot be exported, please use Image layers or Labels layers')

        if export_format == 'tiff':
            export_function = export_stack_as_tiff
        elif export_format == 'h5':
            export_function = export_stack_as_h5
        elif export_format == 'zarr':
            export_function = export_stack_as_zarr
        else:
            raise ValueError(f'{export_format} is not a valid export format, please use tiff or h5')

        # parse metadata in the layer
        if rescale_to_original_resolution and 'original_voxel_size' in image.metadata.keys():
            output_resolution = image.metadata['original_voxel_size']
            input_resolution = image.scale
            scaling_factor = compute_scaling_factor(input_voxel_size=input_resolution,
                                                    output_voxel_size=output_resolution)
        else:
            output_resolution = image.scale
            scaling_factor = None

        voxel_size_unit = image.metadata.get('voxel_size_unit', 'um')
        root_name = image.metadata.get('root_name', 'unknown')

        image_custom_name = None if image_custom_name == '' else image_custom_name
        standard_suffix = f'{i}' if image_custom_name is None else ''

        # run step for the current export
        step_params = {'scaling_factor': scaling_factor,
                       'order': order,
                       'stack_type': stack_type,
                       'dtype': dtype,
                       'custom_name': image_custom_name,
                       'standard_suffix': standard_suffix
                       }

        _ = export_function(data=image.data,
                            name=image.name,
                            directory=directory,
                            voxel_size=output_resolution,
                            voxel_size_unit=voxel_size_unit, **step_params)

        # add step to the workflow dag
        input_keys = (image.name,
                      'out_stack_name',
                      'out_directory',
                      f'{root_name}_voxel_size',
                      f'{root_name}_voxel_size_unit'
                      )

        _export_name = f'{image.name}_export'
        dag_manager.add_step(export_function,
                             input_keys=input_keys,
                             output_key=_export_name,
                             step_name='Export',
                             static_params=step_params)
        export_name.append(_export_name)

        napari_formatted_logging(f'{image.name} Correctly exported, voxel_size: {image.scale} {voxel_size_unit}',
                                 thread='Export stack')

    if export_name:
        # add checkout step to the workflow dag for batch processing
        final_export_check = 'final_export_check'
        dag_manager.add_step(checkout,
                             input_keys=export_name,
                             output_key=final_export_check,
                             step_name='Checkout Execution',
                             static_params={})

        out_path = directory / f'{workflow_name}.pkl'
        dag_manager.export_dag(out_path, final_export_check)
        napari_formatted_logging(f'Workflow correctly exported', thread='Export stack')


export_stacks.directory.hide()
export_stacks.export_format.hide()
export_stacks.rescale_to_original_resolution.hide()
export_stacks.data_type.hide()
export_stacks.workflow_name.hide()


@export_stacks.images.changed.connect
def _on_images_changed(images_list: List[Tuple[Layer, str]]):
    images_list = return_value_if_widget(images_list)
    if len(images_list) > 0:
        export_stacks.directory.show()
        export_stacks.export_format.show()
        export_stacks.rescale_to_original_resolution.show()
        export_stacks.data_type.show()
        export_stacks.workflow_name.show()
    else:
        export_stacks.directory.hide()
        export_stacks.export_format.hide()
        export_stacks.rescale_to_original_resolution.hide()
        export_stacks.data_type.hide()
        export_stacks.workflow_name.hide()
