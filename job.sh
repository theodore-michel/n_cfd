#!/bin/bash
#
#SBATCH --job-name=N_CFD
#SBATCH --output=log.out
#SBATCH --partition=MAIN
#SBATCH --qos=calcul
#
#SBATCH --nodes 1
#SBATCH --ntasks 64
#SBATCH --ntasks-per-core 1
#SBATCH --threads-per-core 1
#SBATCH --time=168:00:00
#

module load gcc openmpi vtk/latest felicia/latest mtc/tsv eigen/latest hdf5/latest cmake/latest git/latest petsc/latest mtc/latest
module load cimlibxx/master
conda activate cimlib # activate environment of the repo, modify name according to yours

python3 create_dataset.py --shapes_directory shapes --num_shapes 50 --params_IHM params_IHM.json --save_shapes --driver /home/tmichel/drivers/Release/cimlib_CFD_driver
