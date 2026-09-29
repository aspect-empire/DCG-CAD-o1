# Synthetic basic case

This case exercises the progressive method without a model API or CATIA. Its
input contains one rectangular compartment, one box-shaped item of equipment,
four mounting holes, and one foundation design zone. Scripted role outcomes
provide deterministic evidence to the same orchestration interfaces used by the
method runtime.

`scene.json` is the single public scene-generator input. It can be assembled
with `gencore.scene_generator.scene.assemble_scene_bundle` and is also covered
by the test suite.

Run from the repository root:

```powershell
$env:PYTHONPATH = "src;."
python examples\basic_case\run.py
```

The example is intentionally synthetic. It is not a member of the complete
evaluation dataset and does not define dataset difficulty classes, splits, or a
hidden acceptance oracle.
