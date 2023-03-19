# The Myth of the Robust-Yet-Fragile Nature of Scale-Free Networks: An Empirical Analysis

**Authors**: Rouzbeh Hasheminezhad, August Bøgh Rønberg, Ulrik Brandes

## Setup (currently only available for GNU/Linux|MacOS)
Clone this GitHub repository. If `conda` is not already installed, download and install [Miniconda](https://docs.conda.io/en/latest/miniconda.html#).\
The following command creates a `conda` environment that includes required dependencies.

```
conda env create -f requirements.yml
```

Activate the new `network_collection` environment in `conda` before executing the following steps in order.

```
conda activate network_collection
```

### Collecting, formatting, and pre-processing networks
The following collects the networks from various repositories and other sources
on the internet. \
The code runs in parallel on all cores, to specify the number of cores change `-1` to the desired `number_of_cores`.

```
python collect.py --cores -1
```