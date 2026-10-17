# Scoped design CPU CI — 18 October 2026, Asia/Calcutta

Separate increment after design pipeline PR #11, as legacy checklist H1 requests.
Enables the active PR bases in the existing frontend workflow and adds
`design-python.yml`, with standard-library geometry on Python 3.11 and model
wiring on Windows Python 3.14, CPU only. The model job uses pinned dependencies,
the official CPU PyTorch index and offline Hugging Face loading, then builds the
wheel. Both jobs retain test reports, use read-only repository permissions and
have ten/twenty-minute ceilings. Actions are pinned to exact verified v7 revisions.

Local YAML structure checks pass: expected jobs, branches, permissions, pinned
actions, offline model loading and timeouts. The official CPU index contains the
torch 2.14.1+cpu CPython 3.14 Windows wheel, matching the observed local runtime.
The parent increment passed 165 scoped tests. No unchanged model tests, training,
data/weight acquisition or scientific benchmark was rerun for this workflow edit.
Hosted execution is pending publication; local checks do not assert it passed.

This implements the current **non-detector** CI scope. Legacy H1 remains open for
its request to run the full historical detector suite on Python 3.11: component 1
is outside the human's current request, and the design model package supports
Python 3.12–3.14. Do not claim all historical repository tests pass.

Sources read: [official setup-python documentation](https://github.com/actions/setup-python)
for interpreter/action syntax; `git ls-remote` of [checkout](https://github.com/actions/checkout),
[setup-python](https://github.com/actions/setup-python) and
[upload-artifact](https://github.com/actions/upload-artifact) for exact tag SHAs;
[official PyTorch CPU index](https://download.pytorch.org/whl/cpu/torch/) for the
observed wheel. These confirm configuration/source availability, not hosted CI,
an institution-approved image or scientific reproducibility.

Validation details and workflow hashes are in
[the JSON snapshot](design-ci-readiness-2026-10-18.json). Independent review,
actual data/assets, target/split/exclusion audits and college-cloud execution
evidence remain required before scientific fitting.
