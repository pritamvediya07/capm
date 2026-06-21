"""Adaptive adversaries (CLAIM-4) - attackers that know CAPM exists.

The non-adaptive injectors in :mod:`attacks.injectors` truthfully declare a low
source class and only inflate the *asserted warrant number*, which the ceiling
trivially caps. That is a mechanism demo, not a robustness result.

This package promotes attacks to first-class adaptive adversaries that
manipulate the parts of a manifest an attacker actually controls:

* the **declared source class** itself (E3.2 origin capture - the experiment
  that proves the headline number is not purely by construction);
* the **declared transformation type** vs. the real one (E3.1);
* the **signature / VC** (E3.3 forgery - must fail);
* **collusion** across multiple relays (E3.4).

Everything here is expressed as an :class:`AdversaryProfile` attached to an
agent in the cross-org harness, so a single benchmark can mix honest and
adaptive agents.
"""

from attacks.adaptive.profiles import (AdversaryProfile, ForgeryMode,
                                        collusion_relay, forgery_relay,
                                        honest_origin, inflated_warrant_origin,
                                        lying_transformation_origin,
                                        manifest_forgery_origin,
                                        origin_capture)

__all__ = [
    "AdversaryProfile", "ForgeryMode", "honest_origin",
    "inflated_warrant_origin", "origin_capture", "lying_transformation_origin",
    "manifest_forgery_origin", "forgery_relay", "collusion_relay",
]
