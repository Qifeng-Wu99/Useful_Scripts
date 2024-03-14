#!/bin/bash

# Description: Activate desired version of CUDA

# Author: Qifeng Wu

if [ $# -ne 1 ]; then
    echo "Usage: $0 <cuda_version_number>"
    echo "Example: $0 12.1"
    exit 1
fi

cuda_version="$1"

if [ -L /usr/local/cuda ]; then
    sudo mv /usr/local/cuda /usr/local/cuda_backup
fi


sudo ln -s "/usr/local/cuda-${cuda_version}" /usr/local/cuda

export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

echo "Symbolic link created for CUDA version ${cuda_version}"

source ~/.bashrc

nvcc --version

