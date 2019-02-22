import os.path
import logging
import logzero
from logzero import logger
import pandas as pd
from BITS.utils import load_pickle, save_pickle, run_command
from .encode import encode_reads, detect_variants


def main():
    args = load_args()

    # Load data
    repr_units = pd.read_csv(args.repr_units_fname, sep='\t', index_col=[0, 1])
    tr_reads = pd.read_csv(args.tr_reads_fname, sep='\t', index_col=0)
    pf = load_pickle(args.peaks_finder_fname)

    # Encode reads by mapping the representative units
    if not os.path.isfile(args.out_pkl_fname):
        encodings, cover_rate = encode_reads(repr_units, tr_reads, pf.peaks, args.n_core)
        save_pickle(encodings, args.out_pkl_fname)
        cover_rate.to_csv("cover_rate", sep='\t')
    else:
        logger.info(f"Load {args.out_pkl_fname}")
        encodings = load_pickle(args.out_pkl_fname)
        pd.read_csv("cover_rate", sep='\t', index_col=0)

    # Detect global variants for each representative unit class
    detect_variants(repr_units, tr_reads, encodings, args.variant_fraction, args.hc)
    save_pickle(encodings, args.out_pkl_fname)


def load_args():
    import argparse
    parser = argparse.ArgumentParser(
        description=("Perform layout of reads based on the representative units given."))

    parser.add_argument(
        "-r",
        "--tr_reads_fname",
        type=str,
        default="tr_reads",
        help=("A file of the TR reads. [tr_reads]"))

    parser.add_argument(
        "-u",
        "--repr_units_fname",
        type=str,
        default="repr_units",
        help=("A file of the representative units generated by dacmaster. [repr_units]"))

    parser.add_argument(
        "-p",
        "--peaks_finder_fname",
        type=str,
        default="peaks_finder.pkl",
        help=("PeaksFinder pickle file which is dacmaster's output. [peaks_finder.pkl]"))

    parser.add_argument(
        "-t",
        "--variant_fraction",
        type=float,
        default=0.15,
        help=("Value of Consed's -t option. 0.0 means all variant sites will be used. [0.15]"))

    parser.add_argument(
        "-H",
        "--hc",
        action="store_true",
        default=False,
        help=("Perform variant calling with homopolymer compressed units. [False]"))

    parser.add_argument(
        "-o",
        "--out_pkl_fname",
        type=str,
        default="encodings.pkl",
        help=("Output pickle file for encodings. [encodings.pkl]"))

    parser.add_argument(
        "-n",
        "--n_core",
        type=int,
        default=1,
        help=("Degree of parallelization. [1]"))

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
