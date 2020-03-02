import hydra
import os
from omegaconf import DictConfig
from hydra import slurm_utils

@hydra.main(config_path="config.yaml")
def my_app(cfg: DictConfig):
    slurm_utils.symlink_hydra(cfg, os.getcwd())
    print(cfg.pretty())

if __name__ == "__main__":
    my_app()
