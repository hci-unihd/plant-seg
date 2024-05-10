# Contribute to PlantSeg

PlantSeg is an open-source project and we welcome contributions from the community. There are many ways to contribute, from writing tutorials or blog posts, improving the documentation, submitting bug reports and feature requests or writing code which can be incorporated into PlantSeg itself.

## Getting Started

To set up the development environment, run:

```bash
mamba env create -f environment-dev.yml
conda activate plant-seg-dev
```

To install PlantSeg in development mode, run:

```bash
pip install -e . --no-deps
```

## Testing

In order to run tests make sure that `pytest` is installed in your conda environment.
You can run your tests simply with `python -m pytest` or `pytest`.
For the latter to work you need to install `plantseg` locally in "develop mode" with `pip install -e .`