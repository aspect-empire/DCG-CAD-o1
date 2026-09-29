# DCG-CAD: Evidence-governed knowledge-state reasoning for progressive CAD generation under incomplete engineering constraints


Engineering CAD generation depends on coordinated reasoning over requirements, constraints, model states, and validation evidence. These elements are distributed across engineering documents, parametric models, and review processes, and their status can change as a design develops. We propose Dynamic Constraint Graph-mediated CAD (DCG-CAD), an evidence-governed method for progressive CAD generation under incomplete engineering constraints. DCG-CAD represents requirements, objects, constraints, parameters, geometric references, operations, validation evidence, and agent decisions in a versioned dynamic design-state graph. Evidence-governed state revision, version-consistency control, dependency-subgraph inference, and incremental recomputation coordinate knowledge updates with parametric CAD execution. Across 165 ship-equipment-foundation tasks, DCG-CAD achieved a task success rate of 93.3%, a constraint satisfaction rate of 92.1%, and a rule-proxy geometric validity rate of 90.3% under the controlled protocol. The results demonstrate how explicit knowledge states and evidence-linked transitions can support traceable CAD decisions and selective model updates as engineering information evolves.

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

from DCG-CAD.scene_generator.scene import assemble_scene_bundle

scene = json.loads(Path("examples/basic_case/scene.json").read_text(encoding="utf-8"))
bundle = assemble_scene_bundle(scene)
print(bundle.validation_report)
```

Run the tests with:

```powershell
python -m pytest -q
```

## Optional integrations


Attention needed!!! To use the pycatia skills provided by DCG-CAD, users need to obtain and install the catia V5 software in a Windows environment. Due to the different COM interfaces of the software, it is not recommended to use catia V6 or higher versions (compatibility may be attempted later). In theory, the method proposed in this article can also be migrated to related software that supports Python operation modeling, such as SolidWorks ,Freecad and OpenSCAD.


Install the model-agent adapter only when needed:

```powershell
python -m pip install -e ".[agent]"
```

On Windows, install the optional CATIA boundary with:

```powershell
python -m pip install -e ".[catia]"
```

## Repository structure

```text
src/DCG-CAD/              method implementation
agents/DCG-CAD_multi_agent/ optional five-role model adapter
examples/basic_case/      synthetic offline example
schemas/                  public data schema
tests/                    deterministic tests
docs/                     method and reproducibility notes
```


## License and citation

Attention needed!!! The paper is currently in the review stage. If you would like to use relevant data or methods, please contact the author team
