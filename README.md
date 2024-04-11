# n_cfd

This repository contains code for launching N CFDs (Computational Fluid Dynamics simulations) with varying input parameters, compressing the results, and outputting them in a dataset format.

## Requirements

1. Install the required packages:

```
pip install -r requirements.txt
```

2. Clone py_util_cimlib for useful cimlib functions

```
git clone https://github.com/pjekenrico/py_util_cimlib.git
```
and follow instructions for install, they are also listed below


3. Clone modified meshio to comply with mtc vtu details.

```
git clone https://github.com/pjekenrico/meshio.git
```

4. Install meshio

```
cd meshio
pip install -e .
cd ../py_util_cimlib
pip install -e .
```

## Code Description

The code in this repository is organized as follows:

- `cfd/`: This folder contains the template setup for the CFD.
- `dataset/`: This folder is created during the run, and is where the compressed results of the CFD simulations are stored. Each simulation is attributed an ID number, its results (.xdmf file and .h5 file for compressed VTUs, and .csv for Efforts/Capteurs if any) are stored in each sub_directory with name "ID". 
- `simu/`: This folder is created during the run, and is where the cfd template is copied, simulation launched, vtu outputed. There is one subdirectory per simulation, with name "ID". After each simulation, the results are compressed and moved to `dataset/` folder before the simulation subdirectory is deleted for better disk space usage. 
- `shapes/`: In the case of this CFD example, the varying simulation parameters are its input meshes. Each mesh is stored in the `shapes/` folder, this is where you store your pool of configurations or parameters (meshes, parameters, etc). 
- `params_IHM.json`: this is the json file containing the CFD's specific IHM parameters, so that you can quickly change IHM paramters for different runs without having to modify CFD template.
- `selected_shapes.txt`: this is a file generated during run if prompted to do so, containing all the different shape IDs and their corresponding file_name. This is a dataframe that allows us to draw random shapes from `shapes/` and save the selection for reuse or other purposes. 
- `job.sh`: contains command to run the job on a slurm cluster. Specify parameters of the main function call and other parameters.
- `create_dataset.py`: core script for launching and handling N CFDs using different simulation input parameters (different meshes, IHM parameters, etc.). This is the function that is called in ``job.sh``, it uses an arg parser to determine input parameters. 

## Usage

To run the code, follow these steps:

1. Install the required Python libraries listed above.
2. Place your mesh files in the `shapes/` folder (``.mesh``, ``.msh``, ``.t`` are handled).
3. If needed, modify the CFD template and `create_dataset.py` to take into account specificities of your run.
4. Modify main function call in ``job.sh`` for parameters (number of CFDs, directory names, etc.)
5. Run ``job.sh``. The code will launch N CFD simulations sequentially and store results in `dataset/`.
5. Retrieve `dataset/`, all set!

## Commits and Contact
For any questions or contributions, don't hesitate to contact me at theodore.michel@minesparis.psl.eu !