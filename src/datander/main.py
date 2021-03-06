from dataclasses import dataclass
from BITS.seq.dazz import db_to_n_blocks
from BITS.util.proc import run_command
from BITS.util.scheduler import Scheduler

dir_name     = "datander"
script_fname = f"{dir_name}/run_datander.sh"
log_fname    = f"{dir_name}/log"


@dataclass(eq=False)
class DatanderRunner:
    """Entry point of datander, a commandline tool for detecting tandem repeat regions from (noisy) reads.
    In ECA, slightly customized datander is used (alignment will NOT be extended to the ends of a read).

    positional arguments:
      @ db_prefix <str> : Prefix of the DB file created with DAZZ_DB put at CWD.

    optional arguments:
      @ read_type <str>       ["CLR"]
          : Input read type. Must be "CLR" or "CCS".
      @ n_core    <int>       [1]
          : Number of cores used in datader.
      @ scheduler <Scheduler> [Scheduler("sge", "qsub", "all.q")]
          : Scheduler object.
    """
    db_prefix    : str
    read_type    : str       = "CLR"
    n_core       : int       = 1
    scheduler    : Scheduler = Scheduler("sge", "qsub", "all.q")

    def __post_init__(self):
        assert self.read_type in ("CLR", "CCS"), "Invalid read type"
        run_command(f"rm -f .{self.db_prefix}.*.tan.* .{self.db_prefix}.tan.* TAN.*")
        run_command(f"mkdir -p {dir_name}; rm -f {dir_name}/*")

    def run(self):
        # Prepare a script to run datander
        # NOTE: error rate of CCS is normally much smaller than 10%, but here it accepts somewhat noisy
        #       self alignments so that sequence diversity of the tandem repeats can be captured.
        options = "" if self.read_type == "CLR" else "-k20 -h50 -e.85 -s500"
        script = run_command(f"HPC.TANmask {options} -T{self.n_core} {self.db_prefix}.db")
        if db_to_n_blocks(f"{self.db_prefix}.db") > 1:
            script += '\n'.join([f"Catrack -v {self.db_prefix} tan",
                                 f"rm .{self.db_prefix}.*.tan.*"])

        # Run the script
        if self.scheduler is None:
            with open(script_fname, "w") as f:
                f.write(f"{script}\n")
            run_command(f"bash {script_fname} > {log_fname} 2>&1")
        else:
            self.scheduler.submit(script,
                                  script_fname,
                                  job_name="datander",
                                  log_fname=log_fname,
                                  n_core=self.n_core,
                                  wait=True)
