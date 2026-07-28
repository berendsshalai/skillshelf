from pathlib import Path

from ..improvement import ProposalStore


def proposal_store(home: Path, root: Path) -> ProposalStore:
    return ProposalStore(home, root)
