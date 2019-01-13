# define base image
FROM ubuntu:latest
# FROM node:7-onbuild

# set maintainer
LABEL maintainer "pyrpl.readthedocs.io@gmail.com"

USER root

ARG CONDA_DIR="/opt/conda"
ARG PYTHON_VERSION="3"

# setup ubuntu
RUN apt update --yes
RUN apt upgrade --yes
RUN apt-get install wget --yes

# install miniconda
RUN mkdir /tmp/miniconda
WORKDIR /tmp/miniconda
#RUN wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
RUN if [ "$PYTHON_VERSION" = "2" ] ; then wget https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh -O Miniconda.sh; else wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O Miniconda.sh; fi
RUN chmod +x Miniconda.sh
RUN ./Miniconda.sh -b -p $CONDA_DIR

# set path environment variable to refer to conda bin dir (we are working in the (base) conda environment
ENV PATH="$CONDA_DIR/bin:$PATH"

# install desired python version and additional packages
RUN conda install --yes python=$PYTHON_VERSION nose coverage numpy pyaudio twine
#RUN conda install --yes -c conda-forge radon
RUN pip install radon

# Clean up miniconda installation files
WORKDIR /
RUN rm -rf /tmp/miniconda

# install additional software
RUN apt-get install --yes sloccount

# auxiliary environment variable
ENV PYTHON_VERSION=$PYTHON_VERSION

# print a message
RUN echo "Docker image is up and running...."
RUN echo $PATH

# print some python diagnostics information
RUN python -V
