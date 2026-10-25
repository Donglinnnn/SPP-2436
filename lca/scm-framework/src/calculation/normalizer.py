from __future__ import annotations

from dataclasses import replace

from .schemas import ProcessInput, ProcessParameterRecord


def normalize_number_text(value: str) -> str:
    """Keep raw numeric text stable for now.

    The function is intentionally simple in this stage to avoid changing existing behavior.
    """
    if value is None:
        return ""
    return str(value).strip()


def normalize_parameter(param: ProcessParameterRecord) -> ProcessParameterRecord:
    return replace(
        param,
        value=normalize_number_text(param.value),
        unit=(param.unit or "").strip(),
        provenance=(param.provenance or "").strip() or None,
        source_note=(param.source_note or "").strip() or None,
        parameter_label=(param.parameter_label or "").strip(),
    )


def normalize_process(process: ProcessInput) -> ProcessInput:
    return ProcessInput(
        process_name=(process.process_name or "").strip(),
        process_order=int(process.process_order),
        parameters=[normalize_parameter(param) for param in process.parameters],
    )
