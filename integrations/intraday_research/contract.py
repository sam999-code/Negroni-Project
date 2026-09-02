"""The GovernedIntradayResearch request contract and its scientific vocabularies.

TASK-085A. A **second** narrow capability, deliberately not an extension of the first.

``HistoricalResearchReplay`` answers *"can the frozen experiment be reproduced exactly?"* —
frozen source, frozen parameters, no hypothesis of its own. This capability answers *"does
an explicitly preregistered new hypothesis show evidence inside a ≤4-hour trading window?"*
The two must not be able to impersonate one another, so they share no contract type, no
capability name and no authorisation object. :data:`CAPABILITY_NAME` differs, and
:meth:`IntradayResearchContract.is_replay_contract` exists solely to make the confusion
impossible to express.

**What the hard invariants are for.** The owner is a day trader whose window closes at four
hours. Every Tier-1 verdict reproduced so far was measured on horizons chosen for other
reasons — H-SWEEP-1 ran 1H horizons out to 48 bars (48 hours), H-SWEEP-2 M15 out to 24 bars
(6 hours). A research layer that *could* express a 24-hour hold under an intraday class would
eventually express one. So the cap is structural: 16 bars at 15m, 4 bars at 1H, and a
contract that refuses at construction rather than warning at review.

**Why context timeframes cannot extend the hold.** 4H/1D/1W are permitted as *information*
and never as an execution frame. A 1W context feature on a 15m decision bar is legitimate; a
1W holding period is not, and :class:`TimeframeSpec` has no way to say the second.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping

__all__ = [
    "CAPABILITY_NAME",
    "CONTEXT_TIMEFRAMES",
    "EXECUTION_TIMEFRAMES",
    "MAXIMUM_HOLDING_MINUTES",
    "CostStatus",
    "EvidenceState",
    "EvidenceSufficiency",
    "IntradayResearchContract",
    "MarketComparison",
    "PortabilityState",
    "ReuseStatus",
    "ResearchRefused",
    "ResearchVerdict",
    "TimeframeComparison",
    "TimeframeSpec",
]

CAPABILITY_NAME: Final = "INTRADAY_HISTORICAL_RESEARCH"
"""Deliberately distinct from ``HISTORICAL_RESEARCH_REPLAY`` and from ``SIMULATE``.

A request naming either of the others cannot satisfy this capability, and a request naming
this one cannot satisfy theirs. Generic SIMULATE remains unsupported in the authority matrix;
this is one bounded research class, not a relaxation of that.
"""

MAXIMUM_HOLDING_MINUTES: Final = 240
"""Four hours. The owner's actual trading window, and a hard structural ceiling."""


@dataclass(frozen=True, slots=True)
class TimeframeSpec:
    """One execution timeframe and the only horizons it may express.

    The bar-count cap is derived from :data:`MAXIMUM_HOLDING_MINUTES`, not stated
    independently, so the two cannot drift apart.
    """

    label: str
    minutes: int
    allowed_bars: tuple[int, ...]

    @property
    def max_bars(self) -> int:
        return MAXIMUM_HOLDING_MINUTES // self.minutes

    def holding_minutes(self, bars: int) -> int:
        return bars * self.minutes

    def validate(self) -> None:
        if MAXIMUM_HOLDING_MINUTES % self.minutes:
            raise ResearchRefused(
                f"{self.label}: {self.minutes}m does not divide the {MAXIMUM_HOLDING_MINUTES}m "
                f"window evenly, so a bar-count cap cannot express it exactly")
        for b in self.allowed_bars:
            if b < 1:
                raise ResearchRefused(f"{self.label}: horizon {b} bars is not positive")
            if b > self.max_bars:
                raise ResearchRefused(
                    f"{self.label}: horizon {b} bars = {self.holding_minutes(b)}m exceeds the "
                    f"{MAXIMUM_HOLDING_MINUTES}m window (max {self.max_bars} bars)")


TF_15M: Final = TimeframeSpec("15m", 15, (1, 2, 4, 8, 16))
TF_1H: Final = TimeframeSpec("1H", 60, (1, 2, 3, 4))
EXECUTION_TIMEFRAMES: Final[Mapping[str, TimeframeSpec]] = MappingProxyType(
    {TF_15M.label: TF_15M, TF_1H.label: TF_1H})
"""The only execution frames this capability supports.

15m caps at 16 bars and 1H at 4 bars — both exactly four hours. Adding a frame means editing
this mapping, which is a reviewable change rather than a request parameter.
"""

CONTEXT_TIMEFRAMES: Final[tuple[str, ...]] = ("4H", "1D", "1W")
"""Permitted as causal *context* only. Never an execution frame, never a holding period."""


class ResearchRefused(Exception):
    """A research request was refused before anything was computed."""


class ReuseStatus(Enum):
    """How much of the confirmation interval has already been seen by earlier work.

    PART 9 forbids manufacturing virgin out-of-sample data. Where none exists, the honest
    outcome is a label, not a workaround — so this vocabulary makes the weaker state sayable.
    """

    VIRGIN_OOS = "virgin_oos"
    PARTIALLY_REUSED_OOS = "partially_reused_oos"
    REUSED_OOS = "reused_oos"
    DEVELOPMENT_ONLY = "development_only"

    @property
    def can_confirm(self) -> bool:
        """Only genuinely unseen data can carry a confirmation claim."""
        return self is ReuseStatus.VIRGIN_OOS

    @property
    def evidence_label(self) -> str:
        return ("CONFIRMATORY EVIDENCE" if self.can_confirm
                else "RESEARCH EVIDENCE — CONFIRMATION REQUIRED")


class CostStatus(Enum):
    COST_VERIFIED = "cost_verified"
    COST_ESTIMATED = "cost_estimated"
    COST_INCOMPLETE = "cost_incomplete"

    @property
    def supports_production_claim(self) -> bool:
        return self is CostStatus.COST_VERIFIED


class ResearchVerdict(Enum):
    """Scientific outcome states. Deliberately not trading grades."""

    SUPPORTED = "supported"
    SUPPORTED_WITH_CONDITIONS = "supported_with_conditions"
    INCONCLUSIVE = "inconclusive"
    REJECTED = "rejected"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    REUSED_OOS_ONLY = "reused_oos_only"
    COST_MODEL_INCOMPLETE = "cost_model_incomplete"
    PORTABILITY_UNTESTED = "portability_untested"

    @property
    def is_tradeable_claim(self) -> bool:
        """Always False. A research verdict is not a signal grade and never becomes one.

        The A++/A+/A/B+ vocabulary belongs to a later, separately authorised layer. Nothing
        here may be translated into it, and this property exists so that the boundary is a
        readable fact rather than a convention someone has to remember.
        """
        return False


class PortabilityState(Enum):
    """Whether an effect found in one instrument is evidenced in another.

    Cross-market transfer is a hypothesis. Currency futures are not spot FX, and GC futures
    are not a gold CFD — the mechanism may transfer, the instrument does not.
    """

    PORTABILITY_UNTESTED = "portability_untested"
    PORTABILITY_SUPPORTED = "portability_supported"
    PORTABILITY_CONDITIONAL = "portability_conditional"
    PORTABILITY_REJECTED = "portability_rejected"


class TimeframeComparison(Enum):
    FIFTEEN_MINUTE_ONLY_EDGE = "15m_only_edge"
    ONE_HOUR_ONLY_EDGE = "1h_only_edge"
    MULTI_TIMEFRAME_EDGE = "multi_timeframe_edge"
    NO_EDGE = "no_edge"
    CONTRADICTORY_TIMEFRAME_RESULT = "contradictory_timeframe_result"


class MarketComparison(Enum):
    MARKET_SPECIFIC = "market_specific"
    CROSS_MARKET_SUPPORTED = "cross_market_supported"
    CROSS_MARKET_CONDITIONAL = "cross_market_conditional"
    NO_CROSS_MARKET_SUPPORT = "no_cross_market_support"


class EvidenceSufficiency(Enum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT_DATA = "insufficient_data"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONTRADICTORY = "contradictory"
    EXTERNAL_SOURCE_REQUIRED = "external_source_required"
    OWNER_DECISION_REQUIRED = "owner_decision_required"

    @property
    def authorises_acquisition(self) -> bool:
        """Always False. Naming a missing source is not permission to obtain it."""
        return False


@dataclass(frozen=True, slots=True)
class EvidenceState:
    """What is known, what is missing, and what would resolve it."""

    sufficiency: EvidenceSufficiency
    reuse: ReuseStatus
    cost: CostStatus
    portability: PortabilityState
    missing: tuple[str, ...] = ()
    resolved_by: tuple[str, ...] = ()
    owner_action: str = ""

    @property
    def is_confirmatory(self) -> bool:
        return (self.sufficiency is EvidenceSufficiency.SUFFICIENT
                and self.reuse.can_confirm
                and self.cost.supports_production_claim)

    def as_dict(self) -> dict:
        return {"sufficiency": self.sufficiency.value, "reuse": self.reuse.value,
                "cost": self.cost.value, "portability": self.portability.value,
                "missing": list(self.missing), "resolved_by": list(self.resolved_by),
                "owner_action": self.owner_action,
                "is_confirmatory": self.is_confirmatory,
                "evidence_label": self.reuse.evidence_label}


_PROJECT = re.compile(r"^PRJ-[A-Z0-9-]{1,32}$")
_EXPERIMENT = re.compile(r"^IR-[0-9]{3}-[A-Z0-9-]{1,48}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class PinnedDataset:
    """One dataset the experiment may read, named by path and content."""

    relative_path: str
    sha256: str
    rows: int
    timeframe: str
    market: str

    def __post_init__(self) -> None:
        if not _SHA256.match(self.sha256):
            raise ResearchRefused(f"{self.relative_path!r}: sha256 must be 64 lowercase hex")
        if self.rows <= 0:
            raise ResearchRefused(f"{self.relative_path!r}: rows must be positive")
        p = self.relative_path.replace("\\", "/")
        if p.startswith("/") or ".." in p.split("/") or ":" in p:
            raise ResearchRefused(f"{self.relative_path!r}: must be a relative path, no traversal")


@dataclass(frozen=True, slots=True)
class IntradayResearchContract:
    """An immutable, fully explicit intraday research request.

    Every field that could change a scientific result is required and digest-covered. There
    are no defaults that could quietly alter an outcome: the cost policy, the multiplicity
    family, the reuse status and the seed manifest all have to be stated, because a study
    whose parameters came partly from the request and partly from ambient state would not be
    the study it described.
    """

    project_id: str
    experiment_id: str
    mechanism_id: str
    hypothesis_version: str
    markets: tuple[str, ...]
    execution_timeframes: tuple[str, ...]
    context_timeframes: tuple[str, ...]
    horizon_manifest: tuple[tuple[str, tuple[int, ...]], ...]
    maximum_holding_minutes: int
    source_manifest: tuple[str, ...]
    dataset_manifest: tuple[PinnedDataset, ...]
    resampling_policy_id: str
    session_policy_id: str
    cost_policy: Mapping[str, object]
    is_oos_policy: Mapping[str, object]
    reuse_status: ReuseStatus
    permutation_policy: Mapping[str, object]
    placebo_policy: Mapping[str, object]
    matched_control_policy: Mapping[str, object]
    multiplicity_policy: Mapping[str, object]
    random_seed_manifest: Mapping[str, int]
    expected_outputs: tuple[str, ...]
    resource_bounds: Mapping[str, int]
    preregistration_sha256: str
    cost_status: CostStatus
    notes: str = ""
    _digest_cache: list = field(default_factory=list, compare=False, repr=False, init=False)

    # ── refusals, all at construction ───────────────────────────────────────
    def __post_init__(self) -> None:
        if not _PROJECT.match(self.project_id):
            raise ResearchRefused(f"project_id {self.project_id!r} is not a PRJ- project")
        if not _EXPERIMENT.match(self.experiment_id):
            raise ResearchRefused(
                f"experiment_id {self.experiment_id!r} must look like IR-001-NAME. A new "
                f"experiment needs a new identity; reusing one hides a changed hypothesis")
        if not self.markets:
            raise ResearchRefused("markets is empty")
        if not self.execution_timeframes:
            raise ResearchRefused("execution_timeframes is empty")

        # PART 4 — the hard timeframe invariants
        if self.maximum_holding_minutes != MAXIMUM_HOLDING_MINUTES:
            raise ResearchRefused(
                f"maximum_holding_minutes must be exactly {MAXIMUM_HOLDING_MINUTES}; got "
                f"{self.maximum_holding_minutes}. The window is the owner's, not the study's")
        for tf in self.execution_timeframes:
            if tf not in EXECUTION_TIMEFRAMES:
                raise ResearchRefused(
                    f"execution timeframe {tf!r} is not supported "
                    f"({sorted(EXECUTION_TIMEFRAMES)}). Context frames are not execution frames")
        for tf in self.context_timeframes:
            if tf not in CONTEXT_TIMEFRAMES:
                raise ResearchRefused(
                    f"context timeframe {tf!r} is not in {CONTEXT_TIMEFRAMES}")
            if tf in EXECUTION_TIMEFRAMES:
                raise ResearchRefused(f"{tf!r} cannot be both context and execution")

        # TASK-086A PART 22. A malformed manifest previously surfaced as a bare ValueError from
        # dict(); it already failed closed, but a governed capability should refuse in its own
        # vocabulary. Validation only — nothing here enters canonical_payload, so no recorded
        # digest moves.
        try:
            declared = dict(self.horizon_manifest)
        except (ValueError, TypeError) as exc:
            raise ResearchRefused(
                f"horizon_manifest must be a sequence of (timeframe, bars) pairs, got "
                f"{self.horizon_manifest!r}: {exc}") from exc
        if set(declared) != set(self.execution_timeframes):
            raise ResearchRefused(
                f"horizon_manifest covers {sorted(declared)} but execution timeframes are "
                f"{sorted(self.execution_timeframes)}; every frame needs declared horizons")
        for tf, bars in declared.items():
            spec = EXECUTION_TIMEFRAMES[tf]
            if not bars:
                raise ResearchRefused(f"{tf}: no horizons declared")
            for b in bars:
                if b < 1:
                    raise ResearchRefused(f"{tf}: horizon {b} bars is not positive")
                if b > spec.max_bars:
                    raise ResearchRefused(
                        f"{tf}: horizon {b} bars = {spec.holding_minutes(b)} minutes exceeds "
                        f"the {MAXIMUM_HOLDING_MINUTES}-minute window (max {spec.max_bars} "
                        f"bars). This is the invariant the intraday class exists to enforce")

        if not self.dataset_manifest:
            raise ResearchRefused("dataset_manifest is empty: an unpinned read is not research")
        pinned_markets = {d.market for d in self.dataset_manifest}
        missing = [m for m in self.markets if m not in pinned_markets]
        if missing:
            raise ResearchRefused(
                f"markets {missing} have no pinned dataset. Every read must be pinned")
        if not self.expected_outputs:
            raise ResearchRefused("expected_outputs is empty")
        if not _SHA256.match(self.preregistration_sha256):
            raise ResearchRefused(
                "preregistration_sha256 must be a sha256. A research request without a frozen "
                "preregistration is a request to decide the hypothesis after seeing the result")
        if not self.random_seed_manifest:
            raise ResearchRefused("random_seed_manifest is empty: no generated seeds are allowed")
        for name, seed in self.random_seed_manifest.items():
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise ResearchRefused(f"seed {name!r} must be an int, got {seed!r}")
        for policy, label in ((self.permutation_policy, "permutation_policy"),
                              (self.placebo_policy, "placebo_policy"),
                              (self.matched_control_policy, "matched_control_policy"),
                              (self.multiplicity_policy, "multiplicity_policy"),
                              (self.cost_policy, "cost_policy"),
                              (self.is_oos_policy, "is_oos_policy")):
            if not policy:
                raise ResearchRefused(
                    f"{label} is empty. PART 3 forbids implicit defaults that could "
                    f"materially alter a scientific result")
        for bound in ("maximum_rows", "maximum_seconds", "maximum_parameter_combinations"):
            if int(self.resource_bounds.get(bound, 0)) <= 0:
                raise ResearchRefused(f"resource_bounds[{bound!r}] must be positive")

    # ── identity ─────────────────────────────────────────────────────────────
    @property
    def canonical_payload(self) -> str:
        """Every scientific field, canonically ordered."""
        return json.dumps({
            "project_id": self.project_id,
            "experiment_id": self.experiment_id,
            "mechanism_id": self.mechanism_id,
            "hypothesis_version": self.hypothesis_version,
            "markets": sorted(self.markets),
            "execution_timeframes": sorted(self.execution_timeframes),
            "context_timeframes": sorted(self.context_timeframes),
            "horizon_manifest": sorted([tf, sorted(b)] for tf, b in self.horizon_manifest),
            "maximum_holding_minutes": self.maximum_holding_minutes,
            "source_manifest": sorted(self.source_manifest),
            "dataset_manifest": sorted([d.relative_path, d.sha256, d.rows, d.timeframe,
                                        d.market] for d in self.dataset_manifest),
            "resampling_policy_id": self.resampling_policy_id,
            "session_policy_id": self.session_policy_id,
            "cost_policy": dict(sorted(self.cost_policy.items())),
            "is_oos_policy": dict(sorted(self.is_oos_policy.items())),
            "reuse_status": self.reuse_status.value,
            "permutation_policy": dict(sorted(self.permutation_policy.items())),
            "placebo_policy": dict(sorted(self.placebo_policy.items())),
            "matched_control_policy": dict(sorted(self.matched_control_policy.items())),
            "multiplicity_policy": dict(sorted(self.multiplicity_policy.items())),
            "random_seed_manifest": dict(sorted(self.random_seed_manifest.items())),
            "expected_outputs": sorted(self.expected_outputs),
            "resource_bounds": dict(sorted(self.resource_bounds.items())),
            "preregistration_sha256": self.preregistration_sha256,
            "cost_status": self.cost_status.value,
        }, sort_keys=True, separators=(",", ":"), default=str)

    @property
    def contract_digest(self) -> str:
        if not self._digest_cache:
            self._digest_cache.append(
                hashlib.sha256(self.canonical_payload.encode("utf-8")).hexdigest())
        return self._digest_cache[0]

    @property
    def experiment_run_id(self) -> str:
        return f"{self.experiment_id}-{self.contract_digest[:16]}"

    # ── the separation from HistoricalResearchReplay (PART 2) ───────────────
    @property
    def is_replay_contract(self) -> bool:
        """Always False. This is a new experiment, never a reproduction of a frozen one.

        Present so that "which capability is this?" is answerable from the object rather
        than from the variable name it happens to be held in.
        """
        return False

    @property
    def capability(self) -> str:
        return CAPABILITY_NAME

    @property
    def authorises_execution(self) -> bool:
        """Always False. Research evidence is not permission to trade on it."""
        return False

    def holding_minutes_for(self, timeframe: str, bars: int) -> int:
        return EXECUTION_TIMEFRAMES[timeframe].holding_minutes(bars)

    def max_holding_minutes_declared(self) -> int:
        """The longest hold this contract can possibly express."""
        return max(EXECUTION_TIMEFRAMES[tf].holding_minutes(max(bars))
                   for tf, bars in self.horizon_manifest)
