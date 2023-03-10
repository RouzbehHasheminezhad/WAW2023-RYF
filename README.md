# Robustness of Preferential-Attachment Graphs:</br> Shifting the Baseline

**Authors**: Rouzbeh Hasheminezhad, August Bøgh Rønberg and Ulrik Brandes

<!---
The preliminary version of the paper is available [**here**]().
But we don't have an official link yet as far as I know.
-->

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
on the internet. Note that this script may take few hours to complete on a personal computer. \

```
python data.py
```

### Analyse networks
The following creates the directory `results/tables/` and generates the paper's tables there.
```
python experiments.py
```

<!---
To ease replication, we provide [**here**](https://polybox.ethz.ch/index.php/s/zN3q3AORlctQtTq) the `results` folder obtained after this step.
Should we do something similar for this project?
-->

### Generating Tables
The following creates the directory `results/tables/` and generates the paper's tables there.
```
python tables.py
```

### Generating Figures
The following creates the directory `results/tables/` and generates the paper's tables there.
```
python tables.py
```

## Citation
If you find this repository useful, please consider citing the conference or journal paper.\
The conference paper can be cited as follows, the journal paper is currently under review.
```
<!---
I don't think we have this yet either.
-->
```

## Contact
In case you have questions, please contact [Rouzbeh Hasheminezhad](mailto:shashemi@ethz.ch).