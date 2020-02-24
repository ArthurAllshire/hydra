import os
import logging
import subprocess
import datetime
import sys

from hydra import utils
from pathlib import Path
from omegaconf import OmegaConf

user = os.environ['USER']
log = logging.getLogger(__name__)

hdd = "/scratch/hdd001/home/" + user
ssd = '/scratch/ssd001/home/' + user

date = datetime.datetime.now().strftime("%Y-%m-%d")

def eval_val(val):
    if 'eval' in str(val):
        return str(eval(val.split(':', 1)[1]))
    else:
        return val

def resolve_name(name):
    name_list = [eval_val(str(name[i])) for i in range(len(name)) if name[i] != None]
    return '_'.join(name_list)

def get_j_dir(cfg):
    return os.path.join(ssd, "slurm", date, resolve_name(cfg.slurm.name))

def get_data_dir(cfg):
    return os.path.join('/scratch', 'ssd001', 'datasets', 'cfg.data.task', 'cfg.data.name')

def write_slurm(cfg):

    # set up run directories
    j_dir = get_j_dir(cfg)

    scripts_dir = os.path.join(j_dir, "scripts")
    if not os.path.exists(scripts_dir):
        Path(scripts_dir).mkdir(parents=True, exist_ok=True)

    # write slurm file
    with open(os.path.join(j_dir, "scripts", resolve_name(cfg.slurm.name) + '.slrm'), 'w') as slrmf:
        slrmf.write(
"""#!/bin/bash
#SBATCH --job-name={0}#
#SBATCH --output={1}/log/%j.out
#SBATCH --error={1}/log/%j.err
#SBATCH --partition={2}
#SBATCH --cpus-per-task={3}
#SBATCH --ntasks-per-node=1
#SBATCH --mem={4}
#SBATCH --gres=gpu:{5}
#SBATCH --nodes=1

bash {1}/scripts/{0}.sh
""".format(
            resolve_name(cfg.slurm.name),
            j_dir,
            cfg.slurm.partition,
            eval_val(cfg.slurm.cpu),
            eval_val(cfg.slurm.mem),
            cfg.slurm.gpu
        ))

def write_sh(cfg, overrides):

    # set up run directories
    j_dir = get_j_dir(cfg)
    hydra_cwd = os.getcwd()
    curr_cwd = utils.get_original_cwd()
    exec_path = os.path.join(curr_cwd, sys.argv[0])

    scripts_dir = os.path.join(j_dir, "scripts")
    if not os.path.exists(scripts_dir):
        Path(scripts_dir).mkdir(parents=True, exist_ok=True)

    with open(os.path.join(j_dir, "scripts", resolve_name(cfg.slurm.name) + '.sh'), 'w') as shf:
        shf.write(
"""#!/bin/bash
ln -s /checkpoint/$USER/$SLURM_JOB_ID {0}/$SLURM_JOB_ID
touch {0}/$SLURM_JOB_ID/DELAYPURGE
. /h/$USER/venv/{2}/bin/activate
python3 {3} {4}
""".format(
            j_dir,
            hydra_cwd,
            cfg.slurm.venv,
            exec_path,
            overrides
        ))

def symlink_hydra(cfg, cwd):
    hydra_dir = os.path.join(get_j_dir(cfg), 'conf')
    log.info('Symlinking {} : {}'.format(cwd, hydra_dir))
    if not os.path.exists(hydra_dir):
        Path(hydra_dir).mkdir(parents=True, exist_ok=True)
    os.symlink(cwd, os.path.join(hydra_dir, os.environ['SLURM_JOB_ID']), target_is_directory=True)

def launch_job(cfg):

    # set up run directories
    j_dir = get_j_dir(cfg)
    log_dir = os.path.join(j_dir, "log")
    if not os.path.exists(log_dir):
        Path(log_dir).mkdir(parents=True, exist_ok=True)

    # launch safe only when < 100 jobs running
    num_running = int(subprocess.run('squeue -u $USER | grep R | wc -l', shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8'))
    while(num_running > 100):
        sleep(10)
    subprocess.run('sbatch {0}/scripts/{1}.slrm --qos normal -x {2}'.format(j_dir, resolve_name(cfg.slurm.name), cfg.slurm.exclude), shell=True)
