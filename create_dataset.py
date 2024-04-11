import json
import random
import numpy as np
import pandas as pd
import argparse
import os
import shutil
import glob
import time
import sys
import gmsh

##################################################
### USEFUL FUNCTIONS:
##################################################
def list_of_args(arg):
    return arg.split(",")

def load_file(file_path:str):
    '''Load data from file_path and return as a pandas DataFrame'''
    df = pd.read_csv(file_path, sep='\t')
    return df

def load_dict(file_path:str):
    '''Load json file as dict'''
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def get_simu_name(directory:str):
    '''Get the simulation name from the directory name,
    assuming the simu name is the last part before "Results" or "Resultats" or "resultats"'''
    if 'Results' in directory:
        return os.path.basename(os.path.normpath(directory)).split('Results')[0]
    elif 'Resultats' in directory:
        return os.path.basename(os.path.normpath(directory)).split('Resultats')[0]
    elif 'resultats' in directory:
        return os.path.basename(os.path.normpath(directory)).split('resultats')[0]
    else:
        return os.path.basename(os.path.normpath(directory))

def get_unique_files(directory:str):
    '''Get all unique files in a directory (no matter the extension, removes duplicates).
    Returns a list of file names without extension.'''
    files = list(set([os.path.splitext(f)[0] for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]))
    return files

def compress_results(directory:str, output_file:str, filtered_increments:int=None):
    '''Compress all the vtu files in a directory (Resultats/2d/) into an xdmf/h5 file, 
    removing the first filtered_increments increments (numerical noise).
    The xdmf file will be named output_file, preferably simulation name.'''
    output_directory = os.path.dirname(output_file)
    output_file_only = os.path.basename(output_file)
    os.system(f'cd {output_directory};')
    vtu_files = glob.glob(os.path.join(directory,"*.vtu"))
    compress_command = f'vtu2h5 {os.path.join(directory, "*.vtu")} --outfile {output_file_only}.xdmf > /dev/null;'
    if filtered_increments:
        for vtu_file in vtu_files:
            file_number = int(os.path.splitext(os.path.basename(vtu_file))[0].split('_')[1])
            if file_number <= filtered_increments:
                os.remove(vtu_file) # remove first 40 iterations (div)
    try: 
        os.system(compress_command)
    except Exception as e:  
        simu_name = get_simu_name(directory)
        print(f'Compression to h5 failed for results of simulation {simu_name}:\n {e}', flush=True)
        return
    return output_file

def format_capteurs(results_dir:str, prefix='Capteurs', save_name:str='CAPTEURS.csv'):
    '''Read all the simu/Resultats/prefix* files and save as csv file.
    results_dir is the directory where the prefix* files are sotred (eg. Efforts.txt). 
    Typically, prefix is Capteurs, Efforts, Forces, etc.'''
    files = [f for f in os.listdir(results_dir) if prefix in f and os.path.isfile(os.path.join(results_dir, f))]
    dfs = []
    for file in files:
        df = pd.read_csv(os.path.join(results_dir, file), sep='\t')
        df = df.dropna(axis=1, how='all')
        dfs.append(df)
    merged_df = pd.concat(dfs, axis=1, join='inner')
    # keep only Temps, CompteurTemps and Cx/Cy
    columns_to_keep = ['CompteurTemps', 'Temps'] + [col for col in merged_df.columns if 'Temps' not in col]
    final_df = merged_df[columns_to_keep]
    final_df = final_df.loc[:, ~final_df.columns.duplicated()]
    # save
    final_df.to_csv(save_name, index=False)
    return 

##################################################
### AUX FUNCTIONS FOR GNN PANELS DATASET CREATION:
##################################################

def l2_norm(config1:np.array, config2:np.array):
    '''Calculate the L2 norm between two configurations'''
    return np.linalg.norm(config1 - config2)

def load_configs(file_path:str):
    '''Load configs from file_path and return as a pandas DataFrame'''
    df = pd.read_csv(file_path, sep='\t')
    return df

def get_config(df:pd.DataFrame, index:int):
    '''From config index, return config as a numpy array of the 6 Theta parameters'''
    config = df[df['Config'] == index].values[0][1:]
    return np.array(config)

def select_random_configs(configs_df:pd.DataFrame, num_configs:int=100, similarity_threshold:float=0.08, save_selection:bool=False):
    '''Select num_configs random configurations from configs_pool dataframe, 
    make sure that configurations are not repeated, and that they respect a certain
    L2 distance threshold between them (avoid configurations that are too similar). 
    Return a dataframe of the selected configurations.'''
    selected_configs = []
    selected_indexes = []
    tries = 0
    while len(selected_configs) < num_configs:
        tries += 1
        random_index = random.choice(configs_df['Config'].values)
        random_config = get_config(df=configs_df, index=random_index)
        if len(selected_configs) == 0:
            selected_configs.append(random_config)
            selected_indexes.append(random_index)
        else:
            distances = [l2_norm(random_config, config) for config in selected_configs]
            if all(distance > similarity_threshold for distance in distances):
                selected_configs.append(random_config)
                selected_indexes.append(random_index)
    selected_df = configs_df[configs_df['Config'].isin(selected_indexes)]
    if save_selection:
        selected_df.to_csv('selected_configs.txt', sep='\t', index=False)
    # print info
    print(f'min {min(distances)}, mean {np.mean(distances)}, max {max(distances)}', flush=True)
    print(f'{tries} tries', flush=True)
    return selected_df

def apply_Hbox123(Hbox123:list, IHM_path:str='./cfd/IHM.mtc'):
    '''In IHM.mtc file, find the lines containing '{ Target= BLMHboxi ' (i=1,2,3), 
    and replace the following values with the ones in Hbox123 list. 
    Make sure that format is correct: { Target= BLMHbox1 0.002 } for example'''
    with open(IHM_path, 'r') as file:
        lines = file.readlines()
    for i in range(3):
        for j, line in enumerate(lines):
            if f'{{ Target= BLMHbox{i+1} ' in line:
                lines[j] = f'{{ Target= BLMHbox{i+1} {Hbox123[i]} }}\n'
    with open(IHM_path, 'w') as file:
        file.writelines(lines)
    return

def format_Efforts(results_dir:str, save_name:str='EFFORTS.csv'):
    '''Read all the /Resultats/Efforts* files and save as csv file '''
    files = [f for f in os.listdir(results_dir) if 'Efforts' in f and os.path.isfile(os.path.join(results_dir, f))]
    dfs = []
    for file in files:
        df = pd.read_csv(os.path.join(results_dir, file), sep='\t')
        df = df.dropna(axis=1, how='all')
        dfs.append(df)
    merged_df = pd.concat(dfs, axis=1, join='inner')
    # keep only Temps, CompteurTemps and Cx/Cy
    columns_to_keep = ['CompteurTemps', 'Temps'] + [col for col in merged_df.columns if 'Temps' not in col]
    final_df = merged_df[columns_to_keep]
    final_df = final_df.loc[:, ~final_df.columns.duplicated()]
    # save
    final_df.to_csv(save_name, index=False)
    return 

def init_run(simu_path:str='./simu', dataset_path:str='./dataset', clean:bool=False):
    '''Initialize the run by creating all necessary directories and removing any existing ones'''
    if clean:
        shutil.rmtree(simu_path)
        shutil.rmtree(dataset_path)
    os.makedirs(simu_path, exist_ok=True)
    os.makedirs(dataset_path, exist_ok=True)
    return

def run_cfd(selected_configs:pd.DataFrame, config_index:int, cfd_template:str='/cfd', dataset_path:str='/dataset', simu_path:str='/simu'):
    '''Prepare cfd simu for a given configuration:
    - create a directory for the simulation (/simu_path/config_index)
    - copy cfd template files to the new directory
    - generate meshes with script_geo2msh.py and config
    - convert all .msh to .t with gmsh4mtc_single_step.py, remove all .msh and .geo
    - launch cfd on 64 cores: mpirun -n 64 /home/tmichel/drivers/Release/cimlib_CFD_driver lanceur/Principale.mtc (catch error if any)'''
    # init paths
    dataset_path = os.path.abspath(dataset_path)
    simu_path = os.path.abspath(simu_path)
    cfd_template = os.path.abspath(cfd_template)

    # create simu repo
    simulation_dir = os.path.join(simu_path, str(config_index))
    abs_simulation_dir = os.path.abspath(simulation_dir)
    os.makedirs(simulation_dir, exist_ok=True)
    shutil.copytree(cfd_template, simulation_dir, dirs_exist_ok=True)

    # generate meshes
    config = get_config(df=selected_configs, index=config_index)
    cd_command = f'cd {abs_simulation_dir};'
    mesh_command = f"python3 script_geo2msh.py {' '.join([str(theta) for theta in config])} > mesh.log;"
    try: 
        os.system(cd_command + mesh_command)
    except Exception as e:
        print(f'Mesh generation failed for config {config_index}:\n {e}', flush=True)
        return
    # convert to .t
    files_msh = glob.glob(os.path.join(abs_simulation_dir, '*.msh'))
    for fmsh in files_msh:
        fmsh = os.path.basename(fmsh)
        convert_command = f'python3 gmsh4mtc_single_step.py {fmsh};'
        try: 
            os.system(cd_command + convert_command)
        except Exception as e:
            print(f'Conversion to .t failed for config {config_index} mesh {fmsh}:\n {e}', flush=True)
            return
    # clean 
    clean_command = f'rm {os.path.join(abs_simulation_dir,"*.msh")} {os.path.join(abs_simulation_dir,"*.geo")};'
    try: 
        os.system(cd_command + clean_command)
        os.system(cd_command + f'cp maillage.t maillagecoarse.t;')
    except Exception as e:
        print(f'Cleaning failed for config {config_index}:\n {e}', flush=True)
        return

    # launch cfd
    n_cores = 8     # 64 partitioning error -> BLM on 1, CFD on 8?
    lock_command = f'touch {os.path.join(abs_simulation_dir, "run.lock")}; '
    blm_command = f'/home/tmichel/drivers/Release/cimlib_CFD_driver lanceur/PrincipaleBLM.mtc > logBLM.out; '
    cpyblm_command = 'cp maillage.t maillage.t.old; cp OutputMesh/Mesh_00010.t maillage.t; '
    cfd_command = f'mpirun -n {n_cores} /home/tmichel/drivers/Release/cimlib_CFD_driver lanceur/Principale.mtc > log.out; '
    try:
        pid = os.fork()
        if pid == 0:
            # Child process
            os.system(cd_command + lock_command + blm_command + cpyblm_command + cfd_command)
            os._exit(0)
        else:
            # Parent process
            os.wait()
    except Exception as e:
        print(f'CFD failed for config {config_index}:\n {e}', flush=True)
        return

    return 

def finish_run(config_index:int, dataset_path:str='/dataset', simu_path:str='/simu'):
    '''Once the cfd has been run for a given configuration,
    - compress the vtu files into xdmf, removing first 40 increments
    - move the xdmf to /dataset
    - concat all the /Resultats/Efforts* files and store in csv file as /dataset/config_index_EFFORTS.csv
    - remove the simulation directory'''
    # init paths
    dataset_path = os.path.abspath(dataset_path)
    simu_path = os.path.abspath(simu_path)
    simulation_dir = os.path.join(simu_path, str(config_index))
    abs_simulation_dir = os.path.abspath(simulation_dir)
    cd_command = f'cd {abs_simulation_dir};'

    # compress into xdmf
    vtu_files = glob.glob(os.path.join(abs_simulation_dir, 'Resultats', '2d', '*.vtu')) 
    for vtu_file in vtu_files:
        file_number = int(os.path.splitext(os.path.basename(vtu_file))[0].split('_')[1])
        if file_number <= 40:
            os.remove(vtu_file) # remove first 40 iterations (div)
    config_folder = os.path.join(dataset_path, str(config_index))
    compress_command = f'vtu2h5 {os.path.join(abs_simulation_dir, "Resultats", "2d", "*.vtu")} --outfile ./{config_index}.xdmf > /dev/null;'
    move_command = f'mkdir {config_folder}; mv ./{config_index}.xdmf {config_folder}; mv ./{config_index}.h5 {config_folder};'
    try: 
        os.system(cd_command + compress_command + move_command)
    except Exception as e:  
        print(f'Compression to h5 failed for config {config_index}:\n {e}', flush=True)
        return
    
    # format Efforts
    try:
        format_Efforts(results_dir=os.path.join(simulation_dir, 'Resultats'), 
                       save_name=os.path.join(config_folder, f'{config_index}_EFFORTS.csv'))
    except Exception as e:
        print(f'Converting Efforts files to csv failed for config {config_index}:\n {e}', flush=True)
        return

    # remove simu repo
    os.system(f'cd ..;')
    shutil.rmtree(abs_simulation_dir)

    return

def parser_gnnpanels():
    '''Simple parser for creating a dataset of random configurations'''
    parser = argparse.ArgumentParser(description='Create a dataset of panel tilt configurations')
    parser.add_argument('--configs_file', 
                        type=str, 
                        default='configs_pool.txt', 
                        help='Path to the file containing all possible configurations')
    parser.add_argument('--num_configs', 
                        type=int, 
                        default=100, 
                        help='Number of configurations/trajectories')
    parser.add_argument('--threshold', 
                        type=float, 
                        default=0.1, 
                        help='Minimum L2 distance between configurations')
    parser.add_argument('--Hbox123',
                        type=list_of_args,
                        default=[0.002, 0.2, 2.0],
                        help='BLM Hbox1/2/3 mesh size parameters for simulation, default yields 20k elements mesh')
    parser.add_argument('--save_configs',
                        action='store_true',
                        help='Flag to save the selected random configurations in txt file, for reuse or tracking')
    parser.add_argument('--generate',
                        action='store_true',
                        help='If selected, will generate num_configs random configurations. If ignored, code will run CFD for all configurations in configs_file.')
    return parser.parse_args()


####################################################
### AUX FUNCTIONS FOR N_CFD BEZIER DATASET CREATION:
####################################################

def get_shapes(directory:str):
    '''Get all unique shapes in a directory (no matter the extension, removes duplicates).
    Returns a list of file names without extension.'''
    shapes = get_unique_files(directory)
    index_list = []
    for shape in shapes:
        index = int(shape.split('_')[-1])
        index_list.append(index)
    df = pd.DataFrame({'Index': index_list, 'Filename': shapes})
    return df

def select_shapes(shapes_df:pd.DataFrame, num_shapes:int=100, save_selection:bool=False):
    '''Select num_shapes unqiue random shapes from shapes_df dataframe, 
    Return a dataframe of the selected shapes for simulation.'''
    if num_shapes > len(shapes_df):
        print(f'Not enough shapes available for unique simulations, only {len(shapes_df)} shapes available.', flush=True)
        return
    selected_shapes = []
    selected_indexes = []
    while len(selected_shapes) < num_shapes:
        random_index = random.choice(shapes_df['Index'].values)
        random_shape = shapes_df[shapes_df['Index'] == random_index]['Filename'].values[0]
        if len(selected_shapes) == 0:
            selected_shapes.append(random_shape)
            selected_indexes.append(random_index)
        else:
            if random_shape not in selected_shapes:
                selected_shapes.append(random_shape)
                selected_indexes.append(random_index)
    selected_df = shapes_df[shapes_df['Index'].isin(selected_indexes)]
    if save_selection:
        selected_df.to_csv('selected_shapes.txt', sep='\t', index=False)
    return selected_df

def convert_shape_to_mtc(shapes_directory:str, shape_file_name:str):
    '''See what extensions shape_file_name has in shapes_directory (maybe multiple mesh extensions),
    and convert to .t if necessary. If .mesh, then convert to .msh first. 
    Return the .t file name.'''
    shape_file_multi = glob.glob(os.path.join(shapes_directory, shape_file_name + '.*'))
    if len(shape_file_multi) == 0:
        print(f'No shape found for {shape_file_name}', flush=True)
        return
    shape_file_extensions = [os.path.splitext(f)[1] for f in shape_file_multi]
    if '.t' in shape_file_extensions:
        return shape_file_name + '.t'
    elif '.msh' in shape_file_extensions:
        convert_command = f'mesh --infile {os.path.join(shapes_directory, shape_file_name + ".msh")} --outfile {os.path.join(shapes_directory, shape_file_name + ".t")};'
        try:
            os.system(convert_command)
        except Exception as e:
            print(f'Conversion to .t failed for shape {shape_file_name}:\n {e}', flush=True)
            return
    elif '.mesh' in shape_file_extensions:
        gmsh.initialize()
        gmsh.open(os.path.join(shapes_directory, shape_file_name + '.mesh'))
        gmsh.write(os.path.join(shapes_directory, shape_file_name + '.msh'))
        gmsh.finalize()
        convert_command = f'mesh --infile {os.path.join(shapes_directory, shape_file_name + ".msh")} --outfile {os.path.join(shapes_directory, shape_file_name + ".t")};'
        try:
            os.system(convert_command)
        except Exception as e:
            print(f'Conversion to .t failed for shape {shape_file_name}:\n {e}', flush=True)
            return

def format_IHM(path_IHM:str='.cfd/IHM.mtc', params_IHM:str='params_IHM.json'):
    '''Format the IHM.mtc file with the given simulation parameters in json file.
    For example { TempsFin: 600, PasDeTemps:0.1, ...}.'''
    params_dict = load_dict(params_IHM)
    with open(path_IHM, 'r') as file:
        lines = file.readlines()
    for j, line in enumerate(lines):
        for key, value in params_dict.items():
            if key in line:
                lines[j] = f'{{ Target= {key} {value} }}\n'
    with open(path_IHM, 'w') as file:
        file.writelines(lines)
    return

def run_cfd_bezier(selected_shapes:pd.DataFrame, shape_index:int, cfd_template:str='/cfd', shape_path:str='/shapes', dataset_path:str='/dataset', simu_path:str='/simu', driver_path:str='/home/tmichel/drivers/Release/cimlib_CFD_driver'):
    '''Prepare cfd simu for a given shape:
    - create a directory for the simulation (/simu_path/shape_index)
    - copy cfd template files to the new directory
    - copy the shape file to the new directory
    - launch cfd on 8 cores: mpirun -n 8 driver_path lanceur/Principale.mtc (catch error if any)'''
    # init paths
    dataset_path = os.path.abspath(dataset_path)
    simu_path = os.path.abspath(simu_path)
    cfd_template = os.path.abspath(cfd_template)

    # create simu repo
    simulation_dir = os.path.join(simu_path, str(shape_index))
    abs_simulation_dir = os.path.abspath(simulation_dir)
    os.makedirs(simulation_dir, exist_ok=True)
    shutil.copytree(cfd_template, simulation_dir, dirs_exist_ok=True)

    # copy shape mesh to simu repo
    shape_file = selected_shapes[selected_shapes['Index'] == shape_index]['Filename'].values[0]
    shape_mesh_file = convert_shape_to_mtc(shapes_directory=shape_path, 
                                           shape_file_name=shape_file)
    if shape_mesh_file is None:
        print(f'No shape found for {shape_index}', flush=True)
        return
    shutil.copy(os.path.join(shape_path, shape_mesh_file), os.path.join(simulation_dir,'channel.t'))

    # launch cfd
    n_cores = 8     # 64 partition
    cd_command = f'cd {abs_simulation_dir};'
    lock_command = f'touch {os.path.join(abs_simulation_dir, "run.lock")}; '
    cfd_command = f'mpirun -n {n_cores} {driver_path} Principale.mtc > log.out; '
    try:
        pid = os.fork()
        if pid == 0:
            # Child process
            os.system(cd_command + lock_command + cfd_command)
            os._exit(0)
        else:
            # Parent process
            os.wait()
    except Exception as e:
        print(f'CFD failed for shape {shape_index}:\n {e}', flush=True)
        return
    return

def finish_run_bezier(shape_index:int, dataset_path:str='/dataset', simu_path:str='/simu', filtered_increments:int=None):
    '''Once the cfd has been run for a given shape,
    - compress the vtu files into xdmf, removing first filtered_increments increments
    - move the xdmf to /dataset
    - concat all the /Resultats/Efforts* files and store in csv file as /dataset/shape_index_EFFORTS.csv
    - remove the simulation directory'''
    # init paths
    dataset_path = os.path.abspath(dataset_path)
    simu_path = os.path.abspath(simu_path)
    simulation_dir = os.path.join(simu_path, str(shape_index))
    abs_simulation_dir = os.path.abspath(simulation_dir)
    cd_command = f'cd {abs_simulation_dir};'


    #   compress into xdmf
    vtu_files = glob.glob(os.path.join(abs_simulation_dir, 'Resultats', '2d', '*.vtu')) 
    compress_command = f'vtu2h5 {os.path.join(abs_simulation_dir, "Resultats", "2d", "*.vtu")} --outfile ./{shape_index}.xdmf > /dev/null;'
    if filtered_increments:
        for vtu_file in vtu_files:
            file_number = int(os.path.splitext(os.path.basename(vtu_file))[0].split('_')[1])
            if file_number <= 40:
                os.remove(vtu_file) # remove first filetered_increments time increments (numerical noise)
    config_folder = os.path.join(dataset_path, str(shape_index))
    move_command = f'mkdir {config_folder}; mv ./{shape_index}.xdmf {config_folder}; mv ./{shape_index}.h5 {config_folder};'
    try: 
        os.system(cd_command + compress_command + move_command)
    except Exception as e:  
        print(f'Compression to h5 failed for shape {shape_index}:\n {e}', flush=True)
        return

    # remove simu repo
    os.system(f'cd ..;')
    shutil.rmtree(abs_simulation_dir)

def parser_bezier():
    '''Simple parser for creating a dataset of random bezier shapes simulations'''
    parser = argparse.ArgumentParser(description='Create a dataset of bezier shapes simulations')
    parser.add_argument('--shapes_directory', 
                        type=str, 
                        default='shapes', 
                        help='Path to the directory containing the bezier shapes (.mesh, .msh, .t)')
    parser.add_argument('--num_shapes', 
                        type=int, 
                        default=10, 
                        help='Number of shapes/CFDs')
    parser.add_argument('--params_IHM',
                        type=str,
                        default='params_IHM.json',
                        help='A json file containing the name of IHM parameters to change and their corresponding values')
    parser.add_argument('--save_shapes',
                        action='store_true',
                        help='Flag to save the selected random shapes in txt file, for reuse or tracking')
    parser.add_argument('--load',
                        action='store_true',
                        help='If ignored, will draw num_shapes random shapes. If selected, code will search for selected_shapes.txt in root, and run corresponding CFDs.')
    parser.add_argument('--driver',
                        type=str,
                        default='/home/tmichel/drivers/Release/cimlib_CFD_driver',
                        help='Path to the cimlib_CFD_driver executable')
    return parser.parse_args()

####################################################
### EXECUTION :
####################################################

def main_gnnpanels():
    # init
    start_time = time.time()
    args = parser_gnnpanels()
    # load configs
    configs_df = load_configs(file_path=args.configs_file)
    if args.generate:
        print(f'Generating {args.num_configs} random configurations...\n', flush=True)
        selected_configs = select_random_configs(configs_df=configs_df, 
                                                 num_configs=args.num_configs, 
                                                 similarity_threshold=args.threshold, 
                                                 save_selection=args.save_configs)
    else: selected_configs = configs_df
    # apply parameters for mesh (20k or 90k)
    apply_Hbox123(Hbox123=args.Hbox123,
                  IHM_path='./cfd/IHM.mtc')
    # for each config, run cfd
    init_run(simu_path='./simu', 
             dataset_path='./dataset', 
             clean=False)
    for config_index in selected_configs['Config'].values:
        print(f'\nTreating config {config_index}...\n', flush=True)
        run_cfd(selected_configs=selected_configs, 
                    config_index=config_index, 
                    cfd_template='./cfd', 
                    dataset_path='./dataset', 
                    simu_path='./simu')
        finish_run(config_index=config_index,
                    cfd_template='./cfd', 
                    dataset_path='./dataset', 
                    simu_path='./simu')
        print(f'Done with config {config_index}.\n     ** Cumulated walltime: {round(time.time() - start_time, 3)} seconds. **\n', flush=True)
    end_time = time.time()
    walltime = round(end_time - start_time,3)
    print(f'Dataset creation complete.\n\n     Walltime: {walltime} seconds.\n', flush=True)

def main_bezier():
    # init
    start_time = time.time()
    args = parser_bezier()
    # load configs
    if args.load:
        print(f'Loading {args.num_shapes} shapes from selected_shapes.txt...\n', flush=True)
        try:
            selected_shapes = load_file(file_path='selected_shapes.txt')
        except Exception as e:
            print(f'Loading selected shapes failed:\n {e}', flush=True)
            return
    else:
        print(f'Choosing {args.num_shapes} random shapes from all possible shapes...\n', flush=True)
        all_shapes = get_shapes(directory=args.shapes_directory)
        selected_shapes = select_shapes(shapes_df=all_shapes,
                                        num_shapes=args.num_shapes,
                                        save_selection=args.save_shapes)
    # apply parameters to IHM
    format_IHM(path_IHM='./cfd/IHM.mtc',
               params_IHM=args.params_IHM)
    # for each config, run cfd
    init_run(simu_path='./simu', 
             dataset_path='./dataset', 
             clean=False)
    for shape_index in selected_shapes['Index'].values:
        print(f'\nTreating shape {shape_index}...\n', flush=True)
        run_cfd_bezier(selected_shapes=selected_shapes, 
                       shape_index=shape_index, 
                       cfd_template='./cfd', 
                       shape_path=args.shapes_directory, 
                       dataset_path='./dataset', 
                       simu_path='./simu', 
                       driver_path=args.driver)
        finish_run_bezier(shape_index=shape_index,
                          dataset_path='./dataset', 
                          simu_path='./simu', 
                          filtered_increments=None)
        print(f'Done with shape {shape_index}.\n     ** Cumulated walltime: {round(time.time() - start_time, 3)} seconds. **\n', flush=True)
    end_time = time.time()
    walltime = round(end_time - start_time,3)
    print(f'Dataset creation complete.\n\n     Walltime: {walltime} seconds.\n', flush=True)



####################################################
### RUN:
####################################################

if __name__ == '__main__':
    # main_gnnpanels()
    main_bezier()
