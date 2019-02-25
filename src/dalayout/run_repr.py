import logging
import logzero
from logzero import logger
import pandas as pd
from BITS.utils import load_pickle, save_pickle, run_command, submit_job


def main():
    args = load_args()

    repr_units = pd.read_csv(args.repr_units_fname, sep='\t', index_col=[0, 1])

    # For each master unit, do again clustering of the synchronized raw units
    run_command("mkdir -p repr; rm -f repr/*")
    jids = []
    for peak_id, repr_id in repr_units.index.values:
        jids.append(submit_job(' '.join([f"calc_repr.py",
                                         f"-e encodings.pkl",
                                         f"-C cover_rate",
                                         f"-r tr_reads",
                                         f"-n {args.n_core}",
                                         f"-p {args.n_distribute}",
                                         f"{peak_id}",
                                         f"{repr_id}"]),
                               f"repr/calc_repr.{peak_id}.{repr_id}.sge",
                               "sge",
                               "qsub",
                               job_name="calc_repr",
                               out_log="repr/log.stdout",
                               err_log="repr/log.stderr",
                               n_core=1,
                               wait=False))

    submit_job("sleep 1s",
               f"repr/gather.gather.sge",
               "sge",
               "qsub",
               job_name="gather_dist_mat",
               out_log="repr/log.stdout",
               err_log="repr/log.stderr",
               n_core=1,
               depend=jids,
               wait=True)

    # Merge the results
    new_repr_units = pd.DataFrame()
    for peak_id, repr_id in repr_units.index.values:
        c = load_pickle(f"repr/clustering.{peak_id}.{repr_id}.pkl")
        new_repr_units = pd.concat([new_repr_units,
                                    c.cons_seqs.assign(peak_id=peak_id) \
                                    .assign(master_id=repr_id) \
                                    .assign(repr_id=range(c.cons_seqs.shape[0]))])
    new_repr_units.reset_index(drop=True) \
                  .reindex(columns=("peak_id",
                                    "master_id",
                                    "repr_id",
                                    "cluster_id",
                                    "cluster_size",
                                    "length",
                                    "sequence")) \
                  .set_index(["peak_id",
                              "master_id",
                              "repr_id"]) \
                  .to_csv("new_repr_units", sep='\t')


def load_args():
    import argparse
    parser = argparse.ArgumentParser(
        description=("Perform layout of reads based on the representative units given."))

    parser.add_argument(
        "-u",
        "--repr_units_fname",
        type=str,
        default="repr_units",
        help=("A file of the representative units generated by dacmaster. [repr_units]"))

    parser.add_argument(
        "-f",
        "--peaks_finder_fname",
        type=str,
        default="peaks_finder.pkl",
        help=("PeaksFinder pickle file which is dacmaster's output. [peaks_finder.pkl]"))

    parser.add_argument(
        "-n",
        "--n_core",
        type=int,
        default=1,
        help=("Degree of parallelization. [1]"))

    parser.add_argument(
        "-p",
        "--n_distribute",
        type=int,
        default=1,
        help=("Degree of parallelization in each distributed job. [1]"))

    parser.add_argument(
        "-j",
        "--job_scheduler",
        type=str,
        default="sge",
        help="Job scheduler name. ('sge' or 'slurm)' [sge]")

    parser.add_argument(
        "-c",
        "--submit_command",
        type=str,
        default="qsub",
        help="Command name to submit a job with the specified scheduler. [qsub]")

    parser.add_argument(
        "-q",
        "--queue_or_partition",
        type=str,
        default=None,
        help="Name of queue (SGE) or partition (SLURM) to which jobs are submitted. [None]")

    parser.add_argument(
        "-D",
        "--debug_mode",
        action="store_true",
        default=False,
        help=("Run in debug mode. [False]"))

    args = parser.parse_args()
    if args.debug_mode:
        logzero.loglevel(logging.DEBUG)
        pd.set_option('expand_frame_repr', False)   # show entire dataframe
    else:
        logzero.loglevel(logging.INFO)
    del args.debug_mode

    return args


if __name__ == "__main__":
    main()
