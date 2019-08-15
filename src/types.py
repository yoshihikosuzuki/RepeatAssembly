from dataclasses import dataclass, field
from typing import List, Dict


@dataclass(frozen=True)
class SelfAlignment:
    """Class for a self alignment. Used in datruf."""
    ab: int
    ae: int
    bb: int
    be: int
        
    @property
    def distance(self):
        return self.ab - self.bb
        
    @property
    def slope(self):
        return round((self.ae - self.ab) / (self.be - self.bb), 3)


@dataclass(eq=False)
class ReadInterval:
    """Class for an abstract interval of a read.
    A tandem repeat (not unit) is represented using this."""
    start: int
    end: int

    @property
    def length(self):
        return self.end - self.start


@dataclass(eq=False)
class TRUnit(ReadInterval):
    """Class for a tandem repeat unit. Equal to ReadInterval with some properties.
    Normally used as instance variable of TRRead."""
    complete : bool = True
    id       : int  = None   # for clustering of units   # TODO: change name based on the clustering method


@dataclass(eq=False)
class Read:
    """Class for a read."""
    seq    : str
    id     : int = None   # for DAZZ_DB
    name   : str = None   # for fasta

    @property
    def length(self):
        assert self.seq is not None, "Sequence is not set"
        return len(self.seq)


@dataclass(eq=False)
class TRRead(Read):
    """Class for a read with TRs. Multiple TRs in a read are not distinguished here."""
    alignments : List[SelfAlignment] = None
    trs        : List[ReadInterval]  = None
    units      : List[TRUnit]        = None
    repr_units : Dict[int, str]      = None   # {cluster_id: str}
