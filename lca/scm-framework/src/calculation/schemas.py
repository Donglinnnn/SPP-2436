from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from src.contracts import parameter_value_text


@dataclass(frozen=True)
class ProcessParameterRecord:
    parameter_code: str
    parameter_label: str
    value: str
    unit: str
    provenance: Optional[str] = None
    source_note: Optional[str] = None


@dataclass(frozen=True)
class ProcessInput:
    process_name: str
    process_order: int
    parameters: list[ProcessParameterRecord] = field(default_factory=list)


@dataclass(frozen=True)
class MaterialInput:
    material_type: str
    material_name: str
    location: str | None = None
    feedstock_burden_rule: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class CalculationRequest:
    """Normalized request object for one project calculation."""

    project_id: int | None = None
    product_type: str = "SCM"
    pathway_name: str | None = None
    reference_product: str = "SCM product"
    system_boundary: str = "A1-A3"
    material: MaterialInput | None = None
    processes: list[ProcessInput] = field(default_factory=list)
    flow_chart: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CalculationRequest":
        material_payload = payload.get("material") or {}
        material = (
            MaterialInput(
                material_type=material_payload.get("material_type", ""),
                material_name=material_payload.get("material_name", ""),
                location=material_payload.get("location"),
                feedstock_burden_rule=material_payload.get("feedstock_burden_rule"),
                note=material_payload.get("note"),
            )
            if material_payload is not None
            else None
        )

        processes = [
            ProcessInput(
                process_name=item.get("process_name", ""),
                process_order=int(item.get("process_order", idx + 1)),
                parameters=[
                    ProcessParameterRecord(
                        parameter_code=param.get("parameter_code", ""),
                        parameter_label=param.get("parameter_label", ""),
                        value=parameter_value_text(param.get("value")),
                        unit=param.get("unit", ""),
                        provenance=param.get("provenance"),
                        source_note=param.get("source_note"),
                    )
                    for param in item.get("parameters", [])
                    if isinstance(param, dict)
                ],
            )
            for idx, item in enumerate(payload.get("processes", []))
            if isinstance(item, dict)
        ]

        return cls(
            project_id=payload.get("project_id"),
            product_type=payload.get("product_type", "SCM"),
            pathway_name=payload.get("pathway_name"),
            reference_product=payload.get("reference_product", "SCM product"),
            system_boundary=payload.get("system_boundary", "A1-A3"),
            material=material,
            processes=processes,
            flow_chart=payload.get("flow_chart", []),
        )


@dataclass(frozen=True)
class CalculationItem:
    process_name: str
    result_code: str
    value: str
    unit: str
    process_order: int | None = None
    process_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CalculationResponse:
    project_id: int | None
    ok: bool
    items: list[CalculationItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    records: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "project_id": self.project_id,
            "items": [
                asdict(item, dict_factory=dict)
                for item in self.items
            ],
            "warnings": self.warnings,
            "errors": self.errors,
            "summary": self.summary,
            "records": self.records,
        }
