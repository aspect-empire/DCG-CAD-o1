"""Deterministic, source-grounded foundation design rules."""

from .calculator import CalculationResult, FoundationCalculator, ParameterDecision
from .compiler import CompiledRulePackage, RuleCompilationError, compile_rule_package, load_default_package
from .evaluator import ThicknessDecision, thickness_for_load
from .schema import RuleClause
from .units import DimensionError, Quantity

__all__ = [
    "CalculationResult",
    "CompiledRulePackage",
    "DimensionError",
    "FoundationCalculator",
    "ParameterDecision",
    "Quantity",
    "RuleClause",
    "RuleCompilationError",
    "ThicknessDecision",
    "compile_rule_package",
    "load_default_package",
    "thickness_for_load",
]
