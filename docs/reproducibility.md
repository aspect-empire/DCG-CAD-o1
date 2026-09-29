# Reproducibility

The included example is synthetic and runs without a hosted model or CATIA. It
uses scripted role evidence to exercise the same orchestration, graph-version,
decision, and validation interfaces used by the method implementation.

## Verify the example

```powershell
$env:PYTHONPATH = "src;."
python examples\basic_case\run.py
```

## Verify the package

```powershell
python -m pytest -q
python -m build
```

The example demonstrates mechanism execution, not the empirical diversity of
the complete evaluation corpus. The expanded dataset, annotations, benchmark
splits, and dataset-level baselines are outside this release.
