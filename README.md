# Warm TDM

*Current documentation can be found at:*

   https://slaclab.github.io/warm-tdm/

# Quick Start
First, initialize the submodules for this repo:
```
git submodule update --init --recursive
```

Then create a conda environment with the latest version of rogue, activate it, and then install the required pip packages into it:
```
conda create -n warm-tdm-env -c tidair-tag -c conda-forge rogue
conda activate warm-tdm-env
pip install -r pip_requirements.txt
```

Lastly, to test that everything is installed correctly you can launch the main gui (without needing any hardware connected) as follows:
```
python software/scripts/warmTdmGui.py --emulate
```