"""Canonical JSON helpers, owned by nobody in particular.

Generic conversions between JSON documents and Python values: sorted keys, exact
fields, strict decoding, no repair. Nothing here knows what a governance record
is, which is why it lives in ``shared`` rather than in ``persistence``.

**Moved here in TASK-071.1 to break a cycle.** ``event_stream`` needs these
helpers for its own codec, and ``persistence`` imports ``approval``,
``decision_ledger``, and ``budget`` in order to store their records — so
``event_stream -> persistence`` closed a loop through every one of them. The
helpers were never persistence-specific; they were merely living there.
:mod:`evolith_core.persistence.codec` re-exports them, so every existing import
still resolves and no caller had to change.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

__all__ = [
    "canonical_bytes",
    "decode_decimal",
    "decode_enum",
    "decode_time",
    "document_of",
    "encode_decimal",
    "encode_time",
    "flag_of",
    "number_of",
    "optional_number",
    "optional_text",
    "optional_time",
    "require_exact_fields",
    "strings_of",
    "text_of",
]


def canonical_bytes(document: Mapping[str, Any]) -> bytes:
    """Return one canonical byte string for ``document``.

    Sorted keys and no separator whitespace, so the encoding is a function of
    the content alone. ``ensure_ascii`` is off because escaping non-ASCII would
    make the bytes depend on which characters a rationale happened to use.
    """
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _no_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    """Return the object, refusing duplicate keys.

    ``json.loads`` keeps the last of a repeated key by default, which means two
    different documents can decode to one record and nothing says which was
    meant. For governance records that is not a tolerable ambiguity.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(
                f"Duplicate JSON key {key!r} in a governance record. Two values "
                f"for one field means the document has two readings and nothing "
                f"says which was intended, so neither is accepted."
            )
        seen[key] = value
    return seen


def document_of(data: bytes) -> dict[str, Any]:
    """Decode bytes into a JSON object, refusing anything else.

    Raises:
        ValueError: On invalid UTF-8, malformed JSON, duplicate keys, or a
            top-level value that is not an object.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"Persisted governance record is not valid UTF-8 ({error}). The "
            f"bytes are not repaired or decoded with a fallback: a record that "
            f"cannot be read is not a record that can be guessed at."
        ) from error
    try:
        document = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Persisted governance record is not well-formed JSON ({error}). "
            f"Truncated or malformed bytes fail closed; nothing is recovered "
            f"from a partial document."
        ) from error
    if not isinstance(document, dict):
        raise ValueError(
            f"Persisted governance record decoded to {type(document).__name__}, "
            f"not an object."
        )
    return document


def require_exact_fields(
    document: Mapping[str, Any], expected: Sequence[str], what: str
) -> None:
    """Raise unless the document has exactly the expected fields.

    Both directions. A missing field would be filled by a default that nobody
    wrote down; an unknown one means the document was produced by something
    this codec does not understand, and reading the part it recognises would be
    deciding that the rest did not matter.
    """
    found = set(document)
    wanted = set(expected)
    missing = sorted(wanted - found)
    unknown = sorted(found - wanted)
    if missing or unknown:
        raise ValueError(
            f"Persisted {what} has the wrong fields: missing {missing}, "
            f"unknown {unknown}. Nothing is defaulted and nothing is ignored — "
            f"a record this codec does not fully understand is not decoded."
        )


def text_of(value: Any, field: str, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"Persisted {what} field {field!r} is {type(value).__name__}, not a "
            f"string."
        )
    return value


def optional_text(value: Any, field: str, what: str) -> str | None:
    return None if value is None else text_of(value, field, what)


def number_of(value: Any, field: str, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"Persisted {what} field {field!r} is {type(value).__name__}, not a "
            f"whole number."
        )
    return value


def optional_number(value: Any, field: str, what: str) -> int | None:
    return None if value is None else number_of(value, field, what)


def flag_of(value: Any, field: str, what: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(
            f"Persisted {what} field {field!r} is {type(value).__name__}, not a "
            f"boolean."
        )
    return value


def encode_time(moment: datetime, field: str, what: str) -> str:
    """Return an ISO-8601 string, refusing a naive datetime.

    Refused at *encode* time as well as decode. A naive datetime stored once is
    a record whose instant depends on where it was written, and no later reader
    can recover what was meant.
    """
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise ValueError(
            f"Refusing to encode {what} field {field!r}: the datetime is naive. "
            f"An instant without an offset means something different on every "
            f"machine, and the Ledger has to order events across them."
        )
    return moment.isoformat()


def decode_time(value: Any, field: str, what: str) -> datetime:
    text = text_of(value, field, what)
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError(
            f"Persisted {what} field {field!r} is not an ISO-8601 datetime: "
            f"{text!r}."
        ) from error
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise ValueError(
            f"Persisted {what} field {field!r} has no timezone offset: {text!r}. "
            f"A naive timestamp is not assumed to be UTC."
        )
    return moment


def optional_time(value: Any, field: str, what: str) -> datetime | None:
    return None if value is None else decode_time(value, field, what)


def encode_decimal(amount: Decimal | None) -> str | None:
    """Return the exact decimal as text, or ``None``.

    Text rather than a JSON number: a float round-trip turns ``0.1`` into
    something that is not ``0.1``, and this field is money an owner agreed to.
    """
    return None if amount is None else str(amount)


def decode_decimal(value: Any, field: str, what: str) -> Decimal | None:
    if value is None:
        return None
    text = text_of(value, field, what)
    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise ValueError(
            f"Persisted {what} field {field!r} is not a decimal: {text!r}."
        ) from error


def decode_enum(value: Any, enumeration: Any, field: str, what: str) -> Any:
    text = text_of(value, field, what)
    try:
        return enumeration(text)
    except ValueError as error:
        raise ValueError(
            f"Persisted {what} field {field!r} is not a valid "
            f"{enumeration.__name__}: {text!r}. An unrecognised value is not "
            f"mapped to a default — a status nobody can read is not a status."
        ) from error


def strings_of(value: Any, field: str, what: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(
            f"Persisted {what} field {field!r} is {type(value).__name__}, not a "
            f"list."
        )
    return tuple(text_of(item, field, what) for item in value)
