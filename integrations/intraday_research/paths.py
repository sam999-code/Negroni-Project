"""Where a governed research artifact may be written, and where it may never be.

TASK-085B PART 1. Closes the gap TASK-085A disclosed and did not fix: ``PreregLedger.path``
and ``ReuseLedger.write(path)`` accepted any caller-supplied path, so *"no Algory write"* was
the caller's discipline rather than a property of the class. IR-001 happened to write outside
Algory. Nothing made it do so.

**Why destination rather than spelling.** A path is judged on where it resolves, never on how
it is written. ``..`` is not forbidden and neither is a junction — both are resolved first and
then judged, which is the same rule :class:`~integrations.algory_read.paths.AlgoryPathPolicy`
uses for reads and for the same reason: a guard that pattern-matches on ``".."`` is defeated by
a junction, and a guard that forbids junctions is defeated by ``..``. Resolution collapses
both.

**Why marker detection rather than a declared root.** Requiring the caller to name the Algory
root would rebuild the gap one layer up — a caller that forgot to declare it would be
unprotected, which is exactly the failure this module exists to remove. So the default policy
declares nothing and *recognises* an Algory checkout by its contents, wherever it is. Explicit
roots are accepted as well, for defence in depth and so a test can protect a temporary
directory.

**Ordering is load-bearing.** The check runs before any ``mkdir``. A guard that refused after
creating parent directories would already have written into Algory to announce that it would
not.

This is the canonical protected-root policy for ``GovernedIntradayResearch``. The replay
capability has an equivalent guard of its own (``HRR-007``, refusing replay storage inside the
Algory root); unifying the two is a separate change and is not authorised here.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Final

from integrations.intraday_research.contract import ResearchRefused

__all__ = [
    "ALGORY_WRITE_TARGET_REFUSED",
    "ALGORY_DECISIVE_MARKER",
    "ALGORY_SUPPORTING_MARKERS",
    "ProtectedRootPolicy",
    "WriteTargetRefused",
]

ALGORY_WRITE_TARGET_REFUSED: Final = "ALGORY_WRITE_TARGET_REFUSED"
"""The refusal state. Named by the owner in TASK-085B PART 1.

Deliberately distinct from the replay sandbox's ``ALGORY_WRITE_ATTEMPT``, which means a write
was *attempted* inside a running sandbox. This one means a target was refused before anything
was opened, created, or resolved into existence.
"""

ALGORY_DECISIVE_MARKER: Final = "algory_os"
"""The directory that identifies an Algory checkout. Nothing else in this vault has one."""

ALGORY_SUPPORTING_MARKERS: Final[tuple[str, ...]] = (
    "strategies", "handoff", "research", "data", "library", "live")
"""Corroborating directories. Two are required alongside the decisive marker.

The decisive marker alone would be enough in practice. Requiring corroboration means a stray
directory that merely happens to be called ``algory_os`` — an archive, an extracted copy, a
scratch folder — is not mistaken for the repository, and a real checkout is still caught even
if one or two of these are absent.
"""

_MINIMUM_SUPPORTING: Final = 2


class WriteTargetRefused(ResearchRefused):
    """A write target resolved somewhere a governed research artifact may not go.

    Subclasses :class:`ResearchRefused` so every existing caller that already refuses to
    proceed on a research refusal keeps doing so without knowing this class exists.
    """

    state: Final = ALGORY_WRITE_TARGET_REFUSED


def looks_like_algory(directory: pathlib.Path) -> bool:
    """Whether ``directory`` is recognisably an Algory checkout.

    Content-based, so it holds wherever the repository lives and on any machine. Requires the
    decisive marker plus :data:`_MINIMUM_SUPPORTING` corroborating directories.
    """
    try:
        if not (directory / ALGORY_DECISIVE_MARKER).is_dir():
            return False
        found = sum(1 for m in ALGORY_SUPPORTING_MARKERS if (directory / m).is_dir())
    except OSError:
        return False               # unreadable is not provably safe, but it is not Algory
    return found >= _MINIMUM_SUPPORTING


@dataclass(frozen=True, slots=True)
class ProtectedRootPolicy:
    """Roots no governed research artifact may be written into.

    Attributes:
        roots: Explicitly protected trees, resolved at construction so every later comparison
            is between two resolved paths. A root that does not exist is accepted rather than
            refused — nothing can be written inside a directory that is not there, and
            refusing would make the policy unusable on a machine without an Algory checkout.
        detect_algory: Whether to recognise an Algory checkout by its contents. Defaults to
            **True**, so the protection does not depend on anyone remembering to declare it.
    """

    roots: tuple[pathlib.Path, ...] = ()
    detect_algory: bool = True
    _resolved: list = field(default_factory=list, compare=False, repr=False, init=False)

    @classmethod
    def canonical(cls, *extra_roots: str | pathlib.Path) -> ProtectedRootPolicy:
        """The default policy: detect Algory by content, plus any extra declared roots."""
        return cls(roots=tuple(pathlib.Path(r) for r in extra_roots), detect_algory=True)

    @property
    def resolved_roots(self) -> tuple[pathlib.Path, ...]:
        if not self._resolved:
            self._resolved.append(tuple(pathlib.Path(r).resolve() for r in self.roots))
        return self._resolved[0]

    def write_target(self, path: str | pathlib.Path, *, what: str = "artifact") -> pathlib.Path:
        """Return the resolved absolute path for ``path``, or refuse.

        Resolution happens first, so ``..``, junctions, symbolic links and relative-path
        aliasing are all judged on where they land. The returned path is the resolved one, so a
        caller that writes to the return value cannot write somewhere else.

        Raises:
            WriteTargetRefused: The target resolves inside a protected root, or inside a
                directory recognisable as an Algory checkout.
        """
        text = str(path)
        if not text.strip():
            raise WriteTargetRefused(f"{ALGORY_WRITE_TARGET_REFUSED}: no {what} path was named")

        resolved = pathlib.Path(text).resolve()

        for root in self.resolved_roots:
            # is_relative_to carries the platform's own case rule: case-insensitive on
            # Windows, case-sensitive on POSIX. Comparing strings would get one of them wrong.
            if resolved == root or resolved.is_relative_to(root):
                raise WriteTargetRefused(
                    f"{ALGORY_WRITE_TARGET_REFUSED}: {text!r} resolves to {str(resolved)!r}, "
                    f"inside the protected root {str(root)!r}. A governed research {what} is "
                    f"never written into a protected tree")

        if self.detect_algory:
            for candidate in (resolved, *resolved.parents):
                if looks_like_algory(candidate):
                    raise WriteTargetRefused(
                        f"{ALGORY_WRITE_TARGET_REFUSED}: {text!r} resolves to "
                        f"{str(resolved)!r}, inside {str(candidate)!r}, which is an Algory "
                        f"checkout ({ALGORY_DECISIVE_MARKER}/ plus corroborating "
                        f"directories). Algory is immutable input to every research "
                        f"capability, so no {what} may be written anywhere beneath it")

        return resolved
