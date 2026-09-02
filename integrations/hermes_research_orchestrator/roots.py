"""Where the research lead may write, and where it may never. HERMES-AUTONOMOUS-RESEARCH-001 PART 1.

**The lead is an observer of Evolith that owns one directory of its own.** Every other module in this
package writes through :class:`HermesLeadRootPolicy`, so "Hermes does not write into Evolith" is a
property of the code rather than a habit of whoever wrote the caller. That distinction is the whole
lesson of TASK-085B: IR-001 happened to write outside Algory, and nothing made it do so.

**Five live evidence roots and two repositories are refused by destination, not by spelling.**
:class:`~integrations.intraday_research.paths.ProtectedRootPolicy` already resolves a target before
judging it, which defeats ``..`` and a junction with one rule instead of two, and it already refuses
an Algory checkout by content. This policy delegates to it and then adds what the research lead needs
and the intraday capability did not: the Evolith repository itself, the vault that contains it, and
the ``Evolith*`` evidence roots that hold prospective market evidence under a weekly seal.

**Why the evidence roots are matched by ancestor directory name.** They are not repositories and have
no marker file to recognise -- ``EvolithSignals`` is a directory of JSONL and nothing else. A content
test would therefore have nothing to test, and the honest alternative is to say plainly that the guard
is nominal for these five and that the Hermes profile deny-list is the layer that actually holds.
Naming them here is defence in depth, not the defence.

**The lead's own root is never defaulted.** A module-level default would put a real machine path in a
repository, and a caller that forgot to pass one would silently write into whatever that path was. The
root is supplied at every call, and a target outside it is refused as loudly as a target inside
Evolith -- a research lead that wrote to an unexpected place is indistinguishable, afterwards, from
one that was pointed at the wrong place on purpose.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Final

from integrations.intraday_research.contract import ResearchRefused
from integrations.intraday_research.paths import ProtectedRootPolicy

__all__ = [
    "HERMES_WRITE_TARGET_REFUSED",
    "EVIDENCE_ROOT_NAMES",
    "REPOSITORY_MARKERS",
    "VAULT_MARKER",
    "HermesLeadRootPolicy",
    "HermesWriteTargetRefused",
    "looks_like_evolith_repository",
]

HERMES_WRITE_TARGET_REFUSED: Final = "HERMES_WRITE_TARGET_REFUSED"
"""The refusal state. Deliberately distinct from ``ALGORY_WRITE_TARGET_REFUSED`` so a reader of an
audit log can tell "the lead was pointed at Algory" from "the lead was pointed outside its own root"."""

EVIDENCE_ROOT_NAMES: Final[tuple[str, ...]] = (
    "EvolithShadowStore", "EvolithSignals", "EvolithResearch",
    "EvolithGovernance", "EvolithExternalTools",
)
"""The five live roots. Held under a weekly sealed-holdout regime; a careless read spends evidence
that cannot be recovered, and a write would be worse. The lead names them only to refuse them."""

VAULT_MARKER: Final = "10-Evolith-Core"
"""The vault directory that contains the repository and every worktree of it."""

REPOSITORY_MARKERS: Final[tuple[str, ...]] = ("evolith_core", "integrations", "pyproject.toml")
"""What identifies an Evolith checkout wherever it lives. All three, so a scratch directory that
merely happens to contain an ``integrations`` folder is not mistaken for the repository."""


class HermesWriteTargetRefused(ResearchRefused):
    """A research-lead write target resolved somewhere the lead may not write.

    Subclasses :class:`ResearchRefused` so every caller that already stops on a research refusal keeps
    stopping without knowing this class exists.
    """

    state: Final = HERMES_WRITE_TARGET_REFUSED


def looks_like_evolith_repository(directory: pathlib.Path) -> bool:
    """Whether ``directory`` is recognisably an Evolith checkout or worktree.

    Content-based, so it holds for the main checkout and for every worktree alike, and on a machine
    where the vault lives somewhere else entirely.
    """
    try:
        return all((directory / marker).exists() for marker in REPOSITORY_MARKERS)
    except OSError:
        return False               # unreadable is not provably safe, but it is not the repository


@dataclass(frozen=True, slots=True)
class HermesLeadRootPolicy:
    """The only door through which this package writes.

    Attributes:
        lead_root: The directory the research lead owns. Every write must land inside it.
        protected: The released protected-root policy, consulted first so an Algory checkout is
            refused by the audited rule rather than by a second copy of it.
    """

    lead_root: pathlib.Path
    protected: ProtectedRootPolicy = field(default_factory=ProtectedRootPolicy.canonical)
    _resolved: list = field(default_factory=list, compare=False, repr=False, init=False)

    @classmethod
    def owning(cls, lead_root: str | pathlib.Path,
               *extra_protected: str | pathlib.Path) -> "HermesLeadRootPolicy":
        """The policy for a lead that owns ``lead_root``.

        Raises:
            HermesWriteTargetRefused: ``lead_root`` is itself somewhere the lead may not write. A lead
                whose whole root was inside Evolith would refuse every individual write for the right
                reason and far too late to be useful, so the root is judged once, here.
        """
        policy = cls(lead_root=pathlib.Path(lead_root),
                     protected=ProtectedRootPolicy.canonical(*extra_protected))
        policy._refuse_forbidden_destination(policy.resolved_lead_root, what="lead root")
        return policy

    @property
    def resolved_lead_root(self) -> pathlib.Path:
        if not self._resolved:
            self._resolved.append(pathlib.Path(self.lead_root).resolve())
        return self._resolved[0]

    def write_target(self, path: str | pathlib.Path, *, what: str = "artifact") -> pathlib.Path:
        """Return the resolved absolute path for ``path``, or refuse.

        Ordering is load-bearing and matches the released policy: everything is judged before any
        directory is created, so a guard never writes into a tree in the course of announcing that it
        will not.

        Raises:
            HermesWriteTargetRefused: The target is outside the lead's root, or inside the Evolith
                repository, the vault, or one of the five live evidence roots.
            WriteTargetRefused: The target is inside an Algory checkout or a declared protected root.
                Raised by the released policy and deliberately not re-wrapped, so the audited refusal
                keeps its own name and its own state.
        """
        text = str(path)
        if not text.strip():
            raise HermesWriteTargetRefused(
                f"{HERMES_WRITE_TARGET_REFUSED}: no {what} path was named")

        resolved = self.protected.write_target(text, what=what)
        self._refuse_forbidden_destination(resolved, what=what)

        root = self.resolved_lead_root
        if resolved != root and not resolved.is_relative_to(root):
            raise HermesWriteTargetRefused(
                f"{HERMES_WRITE_TARGET_REFUSED}: {text!r} resolves to {str(resolved)!r}, outside the "
                f"research lead's own root {str(root)!r}. The lead writes in one place so that "
                f"everything it has ever written can be found, read and deleted in one place")
        return resolved

    def _refuse_forbidden_destination(self, resolved: pathlib.Path, *, what: str) -> None:
        """Refuse a target inside a live evidence root, the vault, or an Evolith checkout."""
        for candidate in (resolved, *resolved.parents):
            if candidate.name in EVIDENCE_ROOT_NAMES:
                raise HermesWriteTargetRefused(
                    f"{HERMES_WRITE_TARGET_REFUSED}: {str(resolved)!r} resolves inside "
                    f"{str(candidate)!r}, a live evidence root under a weekly sealed-holdout regime. "
                    f"The research lead neither reads nor writes prospective market evidence; a "
                    f"{what} placed there would contaminate a seal permanently")
            if candidate.name == VAULT_MARKER:
                raise HermesWriteTargetRefused(
                    f"{HERMES_WRITE_TARGET_REFUSED}: {str(resolved)!r} resolves inside "
                    f"{str(candidate)!r}, the Evolith vault. The lead proposes changes to Evolith as "
                    f"text and hands them back; it does not apply them")
            if looks_like_evolith_repository(candidate):
                raise HermesWriteTargetRefused(
                    f"{HERMES_WRITE_TARGET_REFUSED}: {str(resolved)!r} resolves inside "
                    f"{str(candidate)!r}, an Evolith checkout or worktree. A {what} written into the "
                    f"repository by an unattended loop is a change nobody reviewed")
