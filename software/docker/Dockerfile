FROM ubuntu:22.04
LABEL description="SLAC Warm TDM Electronics environment"

ENV MINICONDA_VERSION="latest"
ENV MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    wget \
    bzip2 \
    ca-certificates \
    libglib2.0-0 \
    libxext6 \
    libsm6 \
    libxrender1 \
    git \
    git-lfs \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create a temporary directory for the Miniconda installer
RUN mkdir -p /tmp/conda && cd /tmp/conda

# Install Miniconda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh \
    && bash miniconda.sh -b -p /opt/conda \
    && rm miniconda.sh \
    && . /opt/conda/bin/activate \
    && conda init \
    && conda activate
ENV PATH=/opt/conda/bin:$PATH

# Add Miniconda to the system path
ENV PATH=/opt/conda/bin:$PATH

# Clean up the temporary directory
RUN rm -rf /tmp/conda

## Installing warm-tdm
RUN conda config --set channel_priority strict
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
RUN conda install -n base conda-libmamba-solver
RUN conda config --set solver libmamba

# Next, clone the SLAC warm elex software/fw repo
# do this wherever you want the sw to be installed.
WORKDIR /usr/local/src
RUN git clone https://github.com/slaclab/warm-tdm.git && \
    chown -R $HOST_USER:$HOST_GROUP /usr/local/src/warm-tdm

WORKDIR /usr/local/src/warm-tdm
# checkout development branch
RUN git checkout main
# clone submodules
RUN sed -i "s/git@github.com:/https:\/\/github.com\//" .gitmodules
RUN sed -i "s/git@github.com:/https:\/\/github.com\//" .git/config 
RUN git submodule update --init --recursive
RUN conda env create -f conda.yml -n warm-tdm-env

ARG HOST_UID=1000
ARG HOST_GID=1000
ARG HOST_USER=hostuser
ARG HOST_GROUP=hostgroup

RUN sed -i 's/^GID_MAX.*/GID_MAX 2147483647/' /etc/login.defs && \
    sed -i 's/^UID_MAX.*/UID_MAX 2147483647/' /etc/login.defs && \
    groupadd -g $HOST_GID $HOST_GROUP && \
    useradd -m -u $HOST_UID -g $HOST_GID -s /bin/bash $HOST_USER --no-log-init && \
    echo "source /opt/conda/etc/profile.d/conda.sh && conda activate warm-tdm-env" \
    >> /home/$HOST_USER/.bashrc