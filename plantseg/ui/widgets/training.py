from concurrent.futures import Future
from pathlib import Path
from typing import Tuple

from magicgui import magicgui
from napari import Viewer
from napari.types import LayerDataTuple

from plantseg import PLANTSEG_MODELS_DIR
from plantseg.training.train import unet_training
from plantseg.utils import list_all_dimensionality
from plantseg.ui.widgets.predictions import ALL_DEVICES
from plantseg.ui.widgets.utils import create_layer_name, start_threading_process, return_value_if_widget, \
    layer_properties


def unet_training_wrapper(dataset_dir, model_name, in_channels, out_channels, patch_size, max_num_iters, dimensionality,
                          sparse, device, **kwargs):
    """
    Wrapper to run unet_training in a thread_worker, this is needed to allow the user to select the device
    in the headless mode.
    """
    return unet_training(dataset_dir, model_name, in_channels, out_channels, patch_size, max_num_iters, dimensionality,
                         sparse, device, **kwargs)


@magicgui(call_button='Run Training',
          dataset_dir={'label': 'Path to the dataset directory',
                       'mode': 'd',
                       'tooltip': 'Select a directory containing train and val subfolders'},
          model_name={'label': 'Trained model name',
                      'tooltip': f'Model files will be saved in f{PLANTSEG_MODELS_DIR}/model_name'},
          in_channels={'label': 'Input channels',
                       'tooltip': 'Number of input channels', },
          out_channels={'label': 'Output channels',
                        'tooltip': 'Number of output channels', },
          dimensionality={'label': 'Dimensionality',
                          'tooltip': 'Dimensionality of the data (2D or 3D). ',
                          'widget_type': 'ComboBox',
                          'choices': list_all_dimensionality()},
          patch_size={'label': 'Patch size',
                      'tooltip': 'Patch size use to processed the data.'},
          max_num_iterations={'label': 'Max number of iterations'},
          sparse={'label': 'Sparse',
                  'tooltip': 'If True, SPOCO spare training algorithm will be used',
                  'widget_type': 'CheckBox'},
          device={'label': 'Device',
                  'choices': ALL_DEVICES}
          )
def widget_unet_training(viewer: Viewer,
                         dataset_dir: Path = Path.home(),
                         model_name: str = 'my-model',
                         in_channels: int = 1,
                         out_channels: int = 1,
                         dimensionality: str = '3D',
                         patch_size: Tuple[int, int, int] = (80, 160, 160),
                         max_num_iterations: int = 40000,
                         sparse: bool = False,
                         device: str = ALL_DEVICES[0]) -> Future[LayerDataTuple]:
    out_name = create_layer_name(model_name, 'training')
    step_kwargs = dict(model_name=model_name, sparse=sparse, dimensionality=dimensionality)
    return start_threading_process(unet_training_wrapper,
                                   runtime_kwargs={
                                       'dataset_dir': dataset_dir,
                                       'model_name': model_name,
                                       'in_channels': in_channels,
                                       'out_channels': out_channels,
                                       'patch_size': patch_size,
                                       'max_num_iters': max_num_iterations,
                                       'dimensionality': dimensionality,
                                       'sparse': sparse,
                                       'device': device
                                   },
                                   step_name='UNet training',
                                   widgets_to_update=[],
                                   input_keys=(model_name, 'training'),
                                   out_name=out_name,
                                   layer_kwarg={'name': out_name, 'scale': None},
                                   layer_type='image',
                                   viewer=viewer,
                                   statics_kwargs=step_kwargs
                                   )


@widget_unet_training.dimensionality.changed.connect
def _on_dimensionality_changed(dimensionality: str):
    dimensionality = return_value_if_widget(dimensionality)
    if dimensionality == '2D':
        patch_size = (1, 256, 256)
    else:
        patch_size = (80, 160, 160)

    widget_unet_training.patch_size.value = patch_size


@widget_unet_training.sparse.changed.connect
def _on_sparse_change(sparse: bool):
    sparse = return_value_if_widget(sparse)
    if sparse:
        widget_unet_training.out_channels.value = 8
    else:
        widget_unet_training.out_channels.value = 1
