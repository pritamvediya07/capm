# Integrating with SAGA (Plane-1 backing)

CAPM is designed to **extend SAGA** (gsiros/saga), not replace it. SAGA gives
you the cross-agent Plane-1 substrate; CAPM adds Plane-2 (provenance + warrant)
on top.

## What SAGA provides

- A **Provider / CA** that agents register with (`saga.ca.CA.get_SAGA_CA`).
- Per-agent **certificates** and a cryptographic **one-time-token (OTK)**
  mechanism for fine-grained inter-agent access control (`saga.common.crypto`).
- A `LocalAgent` ABC with `run(query, initiating_agent, agent_instance)`.

`CAPMAgent` deliberately mirrors that exact `run` signature, so it drops into a
SAGA deployment unchanged.

## What CAPM adds

- A **signed provenance manifest** carried as an application-level payload
  alongside SAGA's OTK tokens.
- A **warrant evaluator** the receiving agent consults before forming beliefs.
- A **VC binding** so the manifest signature is tied to the agent's SAGA
  identity (the Plane-1 ↔ Plane-2 binding, open challenges I6/T4).

## Wiring (standalone → SAGA-backed)

The standalone testbed uses in-process Ed25519 identities and a local
`CredentialRegistry` as a Provider stand-in. To back with real SAGA:

```bash
git clone https://github.com/gsiros/saga.git vendor/saga
pip install -e vendor/saga
export CAPM_USE_SAGA=1
```

Then in `capm/adapters/saga_adapter.py`:

1. `AgentIdentity` is constructed from a SAGA-issued certificate instead of a
   fresh Ed25519 key (the signing interface — `sign` / `verify` — is identical,
   so nothing downstream changes).
2. `CredentialRegistry.trusts(did)` delegates to the SAGA Provider's view of
   registered agents.
3. The CAPM message envelope rides alongside the SAGA OTK exchange: SAGA
   authorises the call (Plane 1); CAPM's manifest accompanies the response and
   is verified by the warrant evaluator (Plane 2).

Because the interfaces already match, the agent and benchmark code is unchanged
between the two configurations — only the backing of `AgentIdentity` and
`CredentialRegistry` swaps.

## Replacing deterministic responders with real LLMs

`CAPMAgent`'s `responder` is `(query, inputs) -> (content, TransformationType)`.
Swap the default for a real model call; classify the transformation the model
performed (verbatim relay vs. paraphrase vs. composition) so the warrant
evaluator can apply the right fidelity penalty. The
`LLM-Latent-Source-Preferences` methodology can be used here to *measure* and
correct the model's latent source bias as part of the warrant score.
