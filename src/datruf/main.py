import argparse
from dataclasses import dataclass
import numpy as np
from logzero import logger
from BITS.seq.dazz import db_to_n_reads
from BITS.util.io import load_pickle, save_pickle
from BITS.util.proc import run_command
from BITS.util.scheduler import Scheduler
from .find_units import find_units

dir_name     = "datruf"
out_fname    = "tr_reads.pkl"
script_scatter_fname = f"{dir_name}/scatter.sh"
script_gather_fname = f"{dir_name}/gather.sh"
log_fname    = f"{dir_name}/log"


@dataclass(eq=False)
class DatrufRunner:
    """Entry point of datruf, which detects units of TRs using the result of datander.

    Positional arguments:
      @ db_fname  <str> : DAZZ_DB `.db` file of the reads.
      @ las_fname <str> : `TAN.*.las` file generated by datander.
    
    Optional arguments:
      @ n_core       <int>       [1]
          : Number of cores for a job. `n_distribute * n_core` cores will be used in total.
      @ n_distribute <int>       [1]
          : Number of jobs to be distributed by datruf.
      @ scheduler    <Scheduler> [Scheduler("sge", "qsub", "all.q")]
          : Scheduler object. Set `scheduler=None` not to use a job scheduler.
    """
    db_fname     : str
    las_fname    : str
    n_core       : int       = 1
    n_distribute : int       = 1
    scheduler    : Scheduler = Scheduler("sge", "qsub", "all.q")

    def __post_init__(self):
        run_command(f"mkdir -p {dir_name}; rm -f {dir_name}/*")

    def run(self):
        n_reads = db_to_n_reads(self.db_fname)

        if self.scheduler is None:
            find_units(1, n_reads, self.n_core, self.db_fname, self.las_fname, out_fname)
            return

        # Split the reads into <n_distribute> blocks and scatter the jobs
        jids = []
        unit_n = -(-n_reads // self.n_distribute)
        for i in range(self.n_distribute):
            index = str(i + 1).zfill(int(np.log10(self.n_distribute) + 1))
            start = 1 + i * unit_n
            end = min([1 + (i + 1) * unit_n - 1, n_reads])
            script = (f"python -m eca.datruf.main {self.db_fname} {self.las_fname} "
                      f"{dir_name}/{out_fname}.{index} {start} {end} {self.n_core}")

            jids.append(self.scheduler.submit(script,
                                              f"{script_scatter_fname}.{index}",
                                              job_name="datruf_scatter",
                                              log_fname=log_fname,
                                              n_core=self.n_core))

        # Merge the results
        logger.info("Waiting for all distributed jobs to be finished...")
        self.scheduler.submit("sleep 1s",
                              script_gather_fname,
                              job_name="datruf_gather",
                              log_fname=log_fname,
                              depend=jids,
                              wait=True)

        merged = []
        fnames = run_command(f"find {dir_name} -name '{out_fname}.*' | sort").strip().split('\n')
        for fname in fnames:
            merged += load_pickle(fname)
        save_pickle(merged, out_fname)


if __name__ == "__main__":
    """Only for internal use by DatrufRunner."""
    p = argparse.ArgumentParser()
    p.add_argument("db_fname", type=str)
    p.add_argument("las_fname", type=str)
    p.add_argument("out_fname", type=str)
    p.add_argument("start_dbid", type=int)
    p.add_argument("end_dbid", type=int)
    p.add_argument("n_core", type=int)
    args = p.parse_args()

    find_units(args.start_dbid, args.end_dbid, args.n_core, args.db_fname, args.las_fname, args.out_fname)
