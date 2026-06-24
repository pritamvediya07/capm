#!/usr/bin/env bash
# Install the realism dependencies WITHOUT sudo, so the E5.x real-attack
# experiments and the E2.1 ProVerif proof run end to end. Idempotent.
#
# Installs:
#   * a venv (.venv) with agentdojo + cryptography  -> E5.4 real AgentDojo
#   * ProVerif 2.05 CLI, built from source via a user-prefix opam (no sudo,
#     no GTK) -> machine-checks proofs/proverif/capm_manifest.pv (E2.1)
#
# After this, run the full realism flow:
#   PATH=$HOME/.local/bin:$PATH .venv/bin/python -m experiments.run_flow
set -e
cd "$(dirname "$0")/.."

echo ">>> [1/3] python venv + agentdojo"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet agentdojo cryptography
.venv/bin/python -c "import agentdojo, cryptography; print('  agentdojo + cryptography OK')"

echo ">>> [2/3] opam (user-prefix, no sudo) + OCaml 4.14.2"
mkdir -p "$HOME/.local/bin"
if ! [ -x "$HOME/.local/bin/opam" ]; then
  curl -fsSL https://github.com/ocaml/opam/releases/download/2.2.1/opam-2.2.1-x86_64-linux \
    -o "$HOME/.local/bin/opam"
  chmod +x "$HOME/.local/bin/opam"
fi
export PATH="$HOME/.local/bin:$PATH"
export OPAMROOT="$HOME/.opam"
opam init --disable-sandboxing --bare -y
opam switch list 2>/dev/null | grep -q '\bcap\b' || opam switch create cap 4.14.2 -y
eval "$(opam env --switch=cap)"

echo ">>> [3/3] ProVerif 2.05 CLI from source (GUI/GTK skipped)"
if ! [ -x "$HOME/.local/bin/proverif" ]; then
  tmp="$(mktemp -d)"; cd "$tmp"
  curl -fsSL https://bblanche.gitlabpages.inria.fr/proverif/proverif2.05.tar.gz -o pv.tar.gz
  tar xzf pv.tar.gz && cd proverif2.05
  ./build || true                      # GUI step fails on missing lablgtk; CLI is built first
  cp proverif "$HOME/.local/bin/proverif"
  chmod +x "$HOME/.local/bin/proverif"
  cd - >/dev/null
fi
"$HOME/.local/bin/proverif" --help 2>&1 | head -1

echo
echo "Done. Run the realism flow with:"
echo "  PATH=\$HOME/.local/bin:\$PATH .venv/bin/python -m experiments.run_flow"
echo "and the ProVerif proof directly with:"
echo "  \$HOME/.local/bin/proverif proofs/proverif/capm_manifest.pv"
