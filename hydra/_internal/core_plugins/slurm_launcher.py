# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence
import os
import time
import sys

from omegaconf import DictConfig, open_dict

from hydra.core.config_loader import ConfigLoader
from hydra.core.config_store import ConfigStore
from hydra.core.hydra_config import HydraConfig
from hydra import utils, slurm_utils
from hydra.core.utils import (
    JobReturn,
    configure_log,
    filter_overrides,
    run_job,
    setup_globals,
)
from hydra.plugins.launcher import Launcher
from hydra.types import TaskFunction

log = logging.getLogger(__name__)

@dataclass
class SlurmLauncherConf:
    _target_: str = "hydra._internal.core_plugins.slurm_launcher.SlurmLauncher"


ConfigStore.instance().store(
    group="hydra/launcher", name="slurm", node=SlurmLauncherConf, provider="hydra"
)

class SlurmLauncher(Launcher):
    def __init__(self) -> None:
        super().__init__()
        self.config: Optional[DictConfig] = None
        self.config_loader: Optional[ConfigLoader] = None
        self.task_function: Optional[TaskFunction] = None

    def setup(
        self,
        config: DictConfig,
        config_loader: ConfigLoader,
        task_function: TaskFunction,
    ) -> None:
        self.config = config
        self.config_loader = config_loader
        self.task_function = task_function

    def launch(
        self, job_overrides: Sequence[Sequence[str]], initial_job_idx: int
    ) -> Sequence[JobReturn]:
        setup_globals()
        assert self.config is not None
        assert self.task_function is not None
        assert self.config_loader is not None

        configure_log(self.config.hydra.hydra_logging, self.config.hydra.verbose)
        sweep_dir = self.config.hydra.sweep.dir
        Path(str(sweep_dir)).mkdir(parents=True, exist_ok=True)
        log.info("Launching {} jobs on slurm".format(len(job_overrides)))
        runs: List[JobReturn] = []

        for idx, overrides in enumerate(job_overrides):
            idx = initial_job_idx + idx
            log.info("\t#{} : {}".format(idx, " ".join(filter_overrides(overrides))))
            sweep_config = self.config_loader.load_sweep_config(
                self.config, list(overrides)
            )

            with open_dict(sweep_config):
                sweep_config.hydra.job.id = idx
                sweep_config.hydra.job.num = idx
            HydraConfig.instance().set_config(sweep_config)

            log.info("\tJob name : {}".format(slurm_utils.resolve_name(sweep_config.slurm.job_name)))

            slurm_utils.write_slurm(sweep_config)
            slurm_utils.write_sh(sweep_config, " ".join(filter_overrides(overrides)))
            slurm_utils.launch_job(sweep_config)

            configure_log(self.config.hydra.hydra_logging, self.config.hydra.verbose)
            if sweep_config.wait:
                time.sleep(1)
        return runs
