# Warm TDM

*Current documentation can be found at:*

   https://slaclab.github.io/warm-tdm/

# Quick Start
First, initialize the submodules for this repo:
```
git submodule update --init --recursive
```

Then use mamba to create a conda environment using the project's conda.yml file, and then activate it:
```
mamba env create --file conda.yml --name warm-tdm-env
mamba activate warm-tdm-env
```

Lastly, to test that everything is installed correctly you can launch the main gui (without needing any hardware connected) as follows:
```
python software/scripts/warmTdmGui.py --emulate
```
