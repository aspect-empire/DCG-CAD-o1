# GenCore method package

GenCore is a selected research-code release for evidence-governed progressive
CAD generation under incomplete engineering constraints. This package exposes
the method core and one synthetic example. It is not the production system, the
complete evaluation corpus, or the dataset planned for a separate release.

## What is included

- versioned dynamic design-state records;
- evidence routing and graph transaction control;
- five bounded engineering-agent roles;
- deterministic decision, validation, and local-repair logic;
- CAD operation contracts with optional CATIA V5 integration;
- one offline synthetic compartment/foundation example.

## Installation

Python 3.10 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

The offline example and test suite do not require CATIA or a model API.

## Offline quick start

```powershell
$env:PYTHONPATH = "src;."
python examples\basic_case\run.py
```

The command replays deterministic role evidence and verifies the resulting
terminal summary against `expected_summary.json`. Runtime files are created in
a temporary directory and are not retained.

The same example includes a minimal scene description. The portable scene
generator can be used directly:

```python
import json
from pathlib import Path

from gencore.scene_generator.scene import assemble_scene_bundle

scene = json.loads(Path("examples/basic_case/scene.json").read_text(encoding="utf-8"))
bundle = assemble_scene_bundle(scene)
print(bundle.validation_report)
```

Run the tests with:

```powershell
python -m pytest -q
```

## Optional integrations

Install the model-agent adapter only when needed:

```powershell
python -m pip install -e ".[agent]"
```

On Windows, install the optional CATIA boundary with:

```powershell
python -m pip install -e ".[catia]"
```

CATIA V5, its license, and COM configuration are not distributed. The core
package imports and the included example remain independent of CATIA. The
public CATIA backend implements session probing and compartment-scene creation;
production foundation construction, model-update, export, and interference
scripts are represented by typed interfaces but are intentionally not included.

## Repository structure

```text
src/gencore/              method implementation
agents/gencore_multi_agent/ optional five-role model adapter
examples/basic_case/      synthetic offline example
schemas/                  public data schema
tests/                    deterministic tests
docs/                     method and reproducibility notes
```

## Release boundary

This release intentionally excludes service credentials, provider endpoints,
experiment databases, web workbenches, runtime logs, generated CAD binaries,
full compartment-scene collections, difficulty labels, hidden oracles, and
train/validation/test splits. Aggregate evidence reported in the associated
paper remains part of the article; the expanded dataset will be versioned and
released separately.

## License and citation

Before uploading this package, select a software license as described in
`LICENSE-DECISION.md`. Citation metadata is provided in `CITATION.cff` and
should be updated with the author list and paper DOI when available.
