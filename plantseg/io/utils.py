from pydantic import BaseModel
import numpy as np
from typing import Protocol, Optional
from pathlib import Path


class VoxelSize(BaseModel):
    """
    Voxel size of an image.
    
    Attributes:
        voxels_size (tuple[float]): Size of the voxels in the image
        unit (str): Unit of the voxel size
    """
    voxels_size: tuple[float] = None
    unit: str = 'um'
    
    
class DataHandler(Protocol):
    """
    Protocol for data handlers. Data handlers are classes that handle data loading, and metadata retrieval.
    """
    path: Optional[Path] = None
    key: Optional[str] = None
    
    def get_data(self) -> np.ndarray:
        pass
    
    def write_data(self, **kwargs) -> None:
        pass
    
    @classmethod
    def from_data_handler(cls, data_handler, **kwargs):
        pass
    
    def get_shape(self) -> tuple[int]:
        pass
    
    def get_voxel_size(self) -> VoxelSize:
        pass
    
    
        