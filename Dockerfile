# define base image
FROM ubuntu:latest
# FROM node:7-onbuild

# set maintainer
LABEL maintainer "pyrpl.readthedocs.io@gmail.com"

USER root

ARG CONDA_DIR="/opt/conda"
ARG PYTHON_VERSION="3"

# setup ubuntu with gui support
RUN apt update --yes
RUN apt upgrade --yes
RUN apt update --yes
RUN apt-get install --yes systemd wget sloccount qt5-default binutils
# sets up keyboard support in GUI
ENV QT_XKB_CONFIG_ROOT /usr/share/X11/xkb

# install miniconda
RUN mkdir /tmp/miniconda
WORKDIR /tmp/miniconda
RUN if [ "$PYTHON_VERSION" = "2" ] ; then wget https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh -O Miniconda.sh; else wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O Miniconda.sh; fi
RUN chmod +x Miniconda.sh
RUN ./Miniconda.sh -b -p $CONDA_DIR

# set path environment variable to refer to conda bin dir (we are working in the (base) conda environment
ENV PATH="$CONDA_DIR/bin:$PATH"
# set library path until pyinstaller issue is fixed
ENV LD_LIBRARY_PATH="$CONDA_DIR/lib:$LD_LIBRARY_PATH"

# install desired python version and additional packages
RUN conda install --yes python=$PYTHON_VERSION numpy scipy paramiko pandas jupyter nose pip pyqt qtpy nbconvert coverage twine matplotlib nb_conda_kernels

# Clean up miniconda installation files
WORKDIR /
RUN rm -rf /tmp/miniconda

# auxiliary environment variable
ENV PYTHON_VERSION=$PYTHON_VERSION

# print a message
RUN echo "Docker image is up and running...."
RUN echo $PATH

# print some python diagnostics information
RUN python -V
