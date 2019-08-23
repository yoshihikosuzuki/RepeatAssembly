from dataclasses import dataclass
import matplotlib.cm as cm
from matplotlib.colors import rgb2hex
from BITS.seq.plot import DotPlot
from BITS.plot.plotly import make_line, make_scatter, make_layout, show_plot
from BITS.util.proc import run_command
from .datruf.io import load_tr_reads
from .datruf.find_units import find_inner_alignments
from .types import TRRead


@dataclass(eq=False)
class ReadViewer:
    """Class for plotting reads in Jupyter Notebook.
    First create an instance of this class with .db and .las files,
    and then show plot by specifying a read ID or TRRead object.
    You can draw self dot plot with Gepard by giving its command.

    Usage example (in Jupyter Notebook):
      > from vca import ReadViewer
      > v = ReadViewer(db_fname, las_fname)
      > v.show(read_id)
    """
    db_fname  : str
    las_fname : str
    gepard    : str = None
    out_dir   : str = "tmp"

    def __post_init__(self):
        run_command(f"mkdir -p {self.out_dir}")

    def show(self, read_id=None, read=None,
             dot_plot=False, alignment_plot=True, plot_size=800, out_html=None):
        """Exactly one of the <read_id> (DAZZ_DB read ID) or <read_obj> (TRRead instance)
        must be given."""
        assert (read_id is None) ^ (read is None), "Specify one of <read_id> [int] or <read> [TRRead]"

        # If <read_id> is specified, create a TRRead object using that.
        if read_id is not None:
            assert isinstance(read_id, int), "<read_id> must be int"
            read = load_tr_reads(read_id, read_id, self.db_fname, self.las_fname)[0]
        else:
            assert isinstance(read, TRRead), "<read> must be TRRead"

        if dot_plot:
            self._dot_plot(read)
        if alignment_plot:
            self._alignment_plot(read, plot_size, out_html)

    def _dot_plot(self, read):
        assert self.gepard is not None, "<gepard> command string must be given"
        assert read.id is not None, "<read>.id must not be None"

        out_fasta = f"{self.out_dir}/{read.id}.fasta"
        run_command(f"DBshow {self.db_fname} {read.id} > {out_fasta}")
        DotPlot(self.gepard, self.out_dir).plot_fasta(out_fasta, out_fasta)

    def _alignment_plot(self, read, plot_size, out_html):
        # <shapes> is a list of (non-interactive) line objects
        shapes = [make_line(0, 0, read.length, read.length, "grey", 3)]   # read
        traces = []

        # Add shapes and traces of TR intervals and self alignments if exist
        if read.trs is not None and read.alignments is not None:
            inner_alignments = find_inner_alignments(read)

            shapes += [make_line(tr.start, tr.start, tr.end, tr.end, "black", 3)
                       for tr in read.trs]   # TRs
            shapes += [make_line(aln.ab, aln.bb, aln.ae, aln.be,   # self alignments
                                 col=("purple" if aln in inner_alignments
                                      else "black" if 0.95 <= aln.slope <= 1.05
                                      else "yellow"),   # abnormal slope (= noisy)
                                 width=3 if aln in inner_alignments else 1)
                       for aln in read.alignments]
            
            # Create traces of start/end positions of the self alignments and TR intervals
            trace_start = make_scatter([aln.ab for aln in read.alignments],
                                       [aln.bb for aln in read.alignments],
                                       name="start")
            trace_end   = make_scatter([aln.ae for aln in read.alignments],
                                       [aln.be for aln in read.alignments],
                                       name="end")
            trace_tr    = make_scatter([tr.start for tr in read.trs],
                                       [tr.start for tr in read.trs],
                                       text=list(range(1, len(read.trs) + 1)),
                                       text_pos="top right", text_size=10, text_col="grey", mode="text",
                                       name="TR interval")
            traces += [trace_start, trace_end, trace_tr]

        # Add shapes and traces of TR units if exist
        if read.units is not None:
            shapes += [make_line(unit.start, unit.start, unit.end, unit.end,
                                 rgb2hex(cm.jet(unit.diff * 3)) if (hasattr(unit, "diff")
                                                                    and unit.diff is not None)
                                 else "black",
                                 5)
                       for unit in read.units]   # on diagonal
            trace_unit = make_scatter([unit.start for unit in read.units],
                                      [unit.start for unit in read.units],
                                      text=[f"{i} " for i in range(len(read.units))],
                                      # TODO: after encoding, f"{df['peak_id']}:{df['master_id']}:{df['repr_id']}{'+' if df['strand'] == 0 else '-'} "
                                      text_pos="bottom left", text_size=10, text_col="black", mode="text",
                                      name="TR unit")
            trace_info = make_scatter([unit.start for unit in read.units],
                                      [unit.start for unit in read.units],
                                      text=[f"unit {i}<br>[{unit.start}:{unit.end}] ({unit.length} bp)"
                                            for i, unit in enumerate(read.units)],
                                      # TODO: after encoding, f"{df.name} ({df['peak_id']}:{df['master_id']}:{df['repr_id']}{'+' if df['strand'] == 0 else '-'})<br>[{df['start']}, {df['end']}] ({df['length']} bp)<br>diff = {df['diff']}"
                                      col="black",
                                      show_legend=False)
            traces += [trace_unit, trace_info]

        # Show plot
        layout = make_layout(plot_size, plot_size, title=f"{read.id}",
                             x_range=[-read.length * 0.05, read.length + 100],
                             y_range=[0, read.length],
                             x_grid=False, y_grid=False, y_reversed=True, shapes=shapes)
        show_plot(traces, layout, out_html)
