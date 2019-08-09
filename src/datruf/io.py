from collections import defaultdict
from logzero import logger
from BITS.util.proc import run_command
from ..types import SelfAlignment, TR, ReadDump


def load_dumps(start_dbid, end_dbid, db_fname, las_fname):
    # Extract data from DBdump's output
    dbdump_command = (f"DBdump -rh -mtan {db_fname} {start_dbid}-{end_dbid} | "
                      f"awk '$1 == \"R\" {{dbid = $2}} "
                      f"$1 == \"T0\" && $2 > 0 {{for (i = 1; i <= $2; i++) "
                      f"printf(\"%s\\t%s\\t%s\\n\", dbid, $(2 * i + 1), $(2 * i + 2))}}'")

    dbdumps = defaultdict(list)
    for line in run_command(dbdump_command).strip().split('\n'):
        read_id, start, end = map(int, line.split('\t'))
        dbdumps[read_id].append(TR(start, end))

    # Extract data from LAdump's output
    ladump_command = (f"LAdump -c {db_fname} {las_fname} {start_dbid}-{end_dbid} | "
                      f"awk '$1 == \"P\" {{dbid = $2}} "
                      f"$1 == \"C\" {{printf(\"%s\\t%s\\t%s\\t%s\\t%s\\n\", dbid, $2, $3, $4, $5)}}'")
    
    ladumps = defaultdict(list)
    for line in run_command(ladump_command).strip().split('\n'):
        read_id, ab, ae, bb, be = map(int, line.split('\t'))
        ladumps[read_id].append(SelfAlignment(ab, ae, bb, be))

    # Merge the data into List[TRRead]
    read_ids = sorted(dbdumps.keys())
    read_dumps = [ReadDump(id=read_id,
                           trs=dbdumps[read_id],
                           alignments=sorted(sorted(ladumps[read_id],
                                                    key=lambda x: x.ab),
                                             key=lambda x: x.distance))
                  for read_id in read_ids]

    return read_dumps


def load_paths(read_dump, inner_alignments, db_fname, las_fname):
    # NOTE: Since alignment path information is very large, load for a single read on demand

    def find_boundary(aseq, bseq):
        # NOTE: "[" and "]" are alignment boundary, "..." is read boundary
        start = aseq.find("[") + 1
        if start == 0:
            while aseq[start] != "." and bseq[start] != ".":
                start += 1
            while aseq[start] == "." or bseq[start] == ".":
                start += 1
        end = aseq.rfind("]")
        if end == -1:
            end = len(aseq)
            while aseq[end - 1] != "." and bseq[end - 1] != ".":
                end -= 1
            while aseq[end - 1] == "." or bseq[end - 1] == ".":
                end -= 1
        return start, end
    
    def convert_symbol(aseq, bseq, symbol):
        return ''.join(['=' if c == "|"
                        else 'I' if aseq[i] == "-"
                        else 'D' if bseq[i] == "-"
                        else 'X'
                        for i, c in enumerate(symbol)])

    if len(read_dump.alignments) == 0:
        return {}

    # Load pairwise alignment information
    command = (f"LAshow4pathplot -a {db_fname} {las_fname} {read_dump.id} | "
               f"sed 's/,//g' | "
               f"awk 'BEGIN {{first = 1}} "
               f"NF == 7 {{if (first == 1) {{first = 0}} "
               f"else {{printf(\"%s\\n%s\\n%s\\n%s\\n\", header, aseq, bseq, symbol)}}; "
               f"header = $0; aseq = \"\"; bseq = \"\"; symbol = \"\"; count = 0;}} "
               f"NF < 7 {{if (count == 0) {{aseq = aseq $0}} "
               f"else if (count == 1) {{symbol = symbol $0}} "
               f"else {{bseq = bseq $0}}; count++; count %= 3;}} "
               f"END {{printf(\"%s\\n%s\\n%s\\n%s\\n\", header, aseq, bseq, symbol)}}'")
    out = run_command(command).strip().split('\n')

    inner_paths = {}
    for header, aseq, bseq, symbol in zip(*([iter(out)] * 4)):    # split every 4 lines (= single entry)
        _, _, ab, ae, bb, be, _ = map(int, header.replace(' ', '').split('\t'))
        alignment = SelfAlignment(ab, ae, bb, be)
        if alignment in inner_alignments:
            # Cut out the flanking regions in aseq, bseq, symbol outside the self alignment,
            # and then convert |, * in symbol into CIGAR characters
            fcigar = convert_symbol(*map(lambda x: x[slice(*find_boundary(aseq, bseq))],
                                         [aseq, bseq, symbol]))
            inner_paths[alignment] = fcigar
    return inner_paths