"""The research lead can reach no execution surface. HERMES-AUTONOMOUS-RESEARCH-001.

**Why this is an architecture test and not a unit test.** Every other guarantee in the package is
about what the lead *does*; this one is about what it is *not able to do*, and a behaviour test cannot
establish an absence. A test that called the lead and observed no order being placed would pass
equally well against a build where an order path existed and simply was not taken on that input.

**The enforcement style is absence, not checking.** These tests assert that the package imports no
broker library, names no order function, and cannot reach the scientific research queue or the signal
watcher -- rather than that some guard rejects a call to one. A guard can be bypassed by a second code
path; a symbol that was never imported cannot be called.

**Docstrings are excluded from the search, and the exclusion is deliberate.** These modules explain in
prose exactly which surfaces they must not reach, and that explanation is the point of the house
style. A grep over raw text would make writing the explanation the thing that failed the test, so the
search runs over the parsed tree: imported module names, called names, attribute names, and string
constants that are not docstrings.

**The scientific queue is out of bounds, and that is the load-bearing one.**
``integrations.research_orchestration`` owns Campaign 001's durable record in ``EvolithResearch``. A
supervisor that could import it could append a supervisor's opinion into a scientific ledger, and
afterwards nothing would distinguish an intention from a finding. The lead therefore cannot name it at
all: it hands briefs to people, and people decide what is appended.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

PACKAGE = pathlib.Path("integrations/hermes_research_orchestrator")

LEAD_MODULES = tuple(sorted(PACKAGE.glob("*.py")))
"""Globbed rather than listed. A new module with no sweep over it would be a new module outside the
firewall, and a hand-maintained list is exactly how one gets there."""

EXECUTION_SURFACES = (
    "order_send", "order_check", "order_calc_margin", "order_calc_profit", "orders_get",
    "positions_get", "position_get", "history_orders_get", "history_deals_get",
    "trade_request", "traderequest", "place_order", "close_position", "modify_order",
    "cancel_order", "send_order", "execute_trade", "open_trade", "copy_trade",
    "symbol_info_tick", "copy_rates_from", "copy_rates_from_pos", "account_info",
)
"""Every name that would place, modify, cancel or read a live position, plus the market readers. The
lead reads no market data either: a supervisor that could pull a tick could answer a research question
by looking, which is the one thing a governed study exists to prevent."""

BROKER_MODULES = ("MetaTrader5", "mt5", "metatrader5", "ccxt", "ib_insync", "oandapyV20")

AUTHORITY_MUTATORS = (
    "set_execution_authority", "grant_execution_authority", "authorise_execution",
    "authorize_execution", "grant_authority", "set_authority", "promote_to_live",
    "assign_grade", "set_grade", "emit_signal", "publish_signal", "confirm_signal",
    "unlock_holdout", "unseal", "set_campaign_authority",
)
"""Names that would grant something. None of them exists here, at any level."""

FORBIDDEN_IMPORTS = (
    "integrations.research_orchestration",
    "integrations.prospective_signals",
    "integrations.signal_alerts",
    "integrations.confirmation_evidence",
    "integrations.sealed_holdout",
    "integrations.shadow_evidence",
    "integrations.execution",
    "integrations.execution_environments",
    "integrations.market_data",
    "integrations.algory_bridge",
    "integrations.algory_read",
    "integrations.research_runtime",
    "evolith_core.execution",
    "evolith_core.approval",
)
"""Two kinds of thing, both refused. The scientific packages, because a supervisor may not write into
a scientific record; and the execution packages, because a supervisor may not reach one. The research
lock is here too: taking Campaign 001's lock would make the lead a second runtime over one campaign,
which is precisely what that lock exists to prevent."""

RUNTIME_ENTRY_POINTS = ("subprocess", "schtasks", "Startup", "win32api", "os.system", "popen")
"""Nothing in this package starts a process. Activation is an owner act, and HERMES-002 builds the
runner; a package that could spawn one would have made the decision this task deferred."""


def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _docstring_nodes(tree: ast.Module) -> set:
    """Node ids of every docstring constant, so prose that *names* a surface is not a use of it."""
    out: set = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                out.add(id(body[0].value))
        # An attribute docstring: a bare string expression following an assignment.
        if isinstance(node, (ast.Module, ast.ClassDef)):
            for statement in getattr(node, "body", []):
                if (isinstance(statement, ast.Expr)
                        and isinstance(statement.value, ast.Constant)
                        and isinstance(statement.value.value, str)):
                    out.add(id(statement.value))
    return out


def _imported_modules(tree: ast.Module) -> set:
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _referenced_names(tree: ast.Module) -> set:
    """Called names, attribute names, and identifiers -- everything a call could go through."""
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _string_constants(tree: ast.Module) -> set:
    docstrings = _docstring_nodes(tree)
    return {node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstrings}


def test_the_package_has_modules_to_sweep():
    """A glob that matched nothing would make every test below pass vacuously."""
    assert len(LEAD_MODULES) >= 7, [str(p) for p in LEAD_MODULES]


@pytest.mark.parametrize("module", LEAD_MODULES, ids=lambda p: p.name)
def test_the_lead_imports_no_broker_library(module):
    imported = _imported_modules(_tree(module))
    for banned in BROKER_MODULES:
        assert not any(name == banned or name.startswith(banned + ".") for name in imported), \
            f"{module} imports {banned}"


@pytest.mark.parametrize("module", LEAD_MODULES, ids=lambda p: p.name)
def test_the_lead_names_no_execution_or_market_surface(module):
    tree = _tree(module)
    referenced = _referenced_names(tree) | _string_constants(tree)
    offending = sorted(set(EXECUTION_SURFACES) & referenced)
    assert not offending, f"{module} names {offending}"


@pytest.mark.parametrize("module", LEAD_MODULES, ids=lambda p: p.name)
def test_the_lead_names_no_broker_module_outside_prose(module):
    """A module name in a string constant would be one ``importlib`` call from being an import."""
    constants = _string_constants(_tree(module))
    for banned in BROKER_MODULES + ("terminal64", "MetaTrader"):
        assert not any(banned.lower() in c.lower() for c in constants), \
            f"{module} carries {banned!r} in a non-docstring string"


@pytest.mark.parametrize("module", LEAD_MODULES, ids=lambda p: p.name)
def test_the_lead_cannot_reach_a_scientific_or_execution_package(module):
    imported = _imported_modules(_tree(module))
    for banned in FORBIDDEN_IMPORTS:
        assert not any(name == banned or name.startswith(banned + ".") for name in imported), \
            f"{module} imports {banned}"


@pytest.mark.parametrize("module", LEAD_MODULES, ids=lambda p: p.name)
def test_the_lead_defines_no_authority_mutator(module):
    tree = _tree(module)
    defined = {node.name for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    referenced = _referenced_names(tree) | _string_constants(tree)
    offending = sorted(set(AUTHORITY_MUTATORS) & (defined | referenced))
    assert not offending, f"{module} names {offending}"


@pytest.mark.parametrize("module", LEAD_MODULES, ids=lambda p: p.name)
def test_the_lead_starts_no_process_and_installs_no_scheduler(module):
    tree = _tree(module)
    imported = _imported_modules(tree)
    referenced = _referenced_names(tree) | _string_constants(tree)
    assert "subprocess" not in imported, f"{module} imports subprocess"
    for banned in RUNTIME_ENTRY_POINTS:
        assert not any(banned.lower() in str(c).lower() for c in referenced
                       if isinstance(c, str)), f"{module} names {banned}"


@pytest.mark.parametrize("module", LEAD_MODULES, ids=lambda p: p.name)
def test_the_lead_reads_no_clock(module):
    """The calling process owns the clock, which is what makes an append testable without a second."""
    imported = _imported_modules(_tree(module))
    assert "datetime" not in imported, f"{module} imports datetime"
    assert "time" not in imported, f"{module} imports time"


@pytest.mark.parametrize("module", LEAD_MODULES, ids=lambda p: p.name)
def test_the_lead_contains_no_unbounded_loop(module):
    """Nothing here is a ``while True``. There is no loop in this package to activate."""
    for node in ast.walk(_tree(module)):
        if isinstance(node, ast.While):
            assert not (isinstance(node.test, ast.Constant) and node.test.value is True), \
                f"{module} contains a while True loop"


def test_the_only_evolith_imports_are_the_shared_helpers_and_the_protected_root_policy():
    """The whole dependency surface, stated once so that widening it is a visible diff."""
    permitted = {
        "evolith_core.shared.canonical_json",
        "integrations.intraday_research.contract",
        "integrations.intraday_research.paths",
    }
    for module in LEAD_MODULES:
        for name in _imported_modules(_tree(module)):
            if name.startswith(("evolith_core", "integrations")):
                assert (name in permitted
                        or name.startswith("integrations.hermes_research_orchestrator")), \
                    f"{module} imports {name}, which is outside the declared dependency surface"
