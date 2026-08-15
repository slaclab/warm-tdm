#!/bin/bash
# Install the conda environment
conda env create -f conda.yml -n warm-tdm-env

# Get the install directory (wherever this script was run from)
INSTALL_DIR=$(pwd)

# Write the activation script into the new environment
ACTIVATE_DIR=$(conda run -n warm-tdm-env sh -c 'echo $CONDA_PREFIX')/etc/conda/activate.d
mkdir -p "$ACTIVATE_DIR"

cat > "$ACTIVATE_DIR/env_vars.sh" << EOF
#!/bin/bash
export WARM_TDM_PATH="$INSTALL_DIR"
EOF

echo "WARM_TDM_PATH set to $INSTALL_DIR"
