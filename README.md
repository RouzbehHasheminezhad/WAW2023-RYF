# The Myth of the Robust-Yet-Fragile Nature of Scale-Free Networks: An Empirical Analysis

**Authors**: Rouzbeh Hasheminezhad, August Bøgh Rønberg, Ulrik Brandes

## Setup (currently only available for GNU/Linux|MacOS)
Clone this GitHub repository. If `conda` is not already installed, download and
install [Miniconda](https://docs.conda.io/en/latest/miniconda.html#).\

### Environment setup
This step sets up the environment in which all the following steps will run. \

The following command creates a `conda` environment that includes required
dependencies.

```
conda env create -f environment.yml
```

Activate the new `WAW` environment in `conda` before executing the following steps in order.

```
conda activate WAW
```

### Collecting, formatting, and pre-processing networks
In this step the networks from various repositories and other sources
on the internet are collected, formatted and pre-processed.\

The code runs in parallel on all cores, to specify the number of cores change
`-1` to the desired `number_of_cores`.

```
python collect.py --cores -1
```

After this finishes running a new directory 'datasets' will have been added to
the repo containing all the networks.\

### Robustness analysis
In this step the robustness of the networks are analyzed. \

```
python analysis.py
```

After this finishes running the 'datasets' directory will have been modified to
also contain the robustness scores for each network. \

### Visualizations
In this step the 4 figures used in the paper are generated using the collected
and analyzed datasets from the previous steps.

```
python figures.py
```

After this finishes running a new directory 'figures' will have been added to
the repo containing all the generated figures.\