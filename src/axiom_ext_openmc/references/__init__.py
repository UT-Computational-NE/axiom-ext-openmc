# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Reference solutions declared by this extension, and the guard that keeps
provisional ones out of verification.

A reference module seeds the *structure* of a benchmark comparison long before
domain reviewers have extracted the real numbers from the source document. Those
seeded numbers are placeholders. Installed silently, they make verification axis
A3 ("does the computed value agree with the published reference?") return a
green result against a value nobody ever published — which is strictly worse
than having no reference at all, because a missing reference is visible and a
fabricated agreement is not.

So every :class:`ReferenceSpec` carries ``provisional``, and
:func:`install_specs` **refuses provisional references by default**. Verification
that has no reference reports "no reference"; it never reports agreement.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, fields, is_dataclass
from typing import Any, Iterable, Protocol

logger = logging.getLogger(__name__)

__all__ = ["ReferenceRegistry", "install_specs"]


class ReferenceRegistry(Protocol):
    """Anything with ``.register(reference)``."""

    def register(self, reference: Any) -> Any: ...


_SPEC_ATTRS = ("uri", "value", "uncertainty", "unit", "source", "citation", "provisional")


def _payload(spec: Any) -> dict[str, Any]:
    """Read a spec into a plain dict, dataclass or not."""
    if is_dataclass(spec) and not isinstance(spec, type):
        return asdict(spec)
    return {a: getattr(spec, a) for a in _SPEC_ATTRS if hasattr(spec, a)}


def _as_reference(spec: Any) -> Any:
    """Adapt a spec to the consumer's Reference type when one is importable.

    ``provisional`` is our own bookkeeping and predates nothing downstream, so
    the payload is filtered to the fields the consumer's Reference actually
    declares. Passing an unknown keyword would make installation fail for every
    consumer that has not yet added the field, which is a worse outcome than
    dropping a flag they do not consult.
    """
    payload = _payload(spec)
    try:
        from neutron_os.extensions.builtins.twin.references import Reference
    except ImportError:
        return payload

    accepted = {f.name for f in fields(Reference)}
    return Reference(**{k: v for k, v in payload.items() if k in accepted})


def install_specs(
    specs: Iterable[Any],
    registry: ReferenceRegistry,
    *,
    include_provisional: bool = False,
) -> int:
    """Install ``specs`` into ``registry``; return how many were installed.

    Provisional specs are skipped unless ``include_provisional`` is set, and the
    skip is logged by URI so an operator can see which comparisons are
    unavailable rather than wondering why a case never verifies.

    Set ``include_provisional=True`` only for structural tests that assert on
    wiring. It must never be set on a path that reports agreement to a user.
    """
    installed = 0
    skipped: list[str] = []

    for spec in specs:
        if getattr(spec, "provisional", False) and not include_provisional:
            skipped.append(spec.uri)
            continue
        registry.register(_as_reference(spec))
        installed += 1

    if skipped:
        logger.warning(
            "Skipped %d provisional reference(s) — these cases cannot be "
            "verified until real values are extracted from the source "
            "document: %s",
            len(skipped),
            ", ".join(skipped),
        )

    return installed
