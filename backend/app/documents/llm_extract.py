"""One-shot LLM structured extraction. Document extraction only, never medical advice."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.documents.structured import ExtractedBiomarker, ExtractedHealthDocument, ExtractedRisk
from app.llm.factory import get_llm_client
from app.pipeline.lab_parameters import display_name_for, primary_lab_key

logger = logging.getLogger("cura.documents")

EXTRACTION_INSTRUCTIONS = """You extract structured facts from a medical document.

Rules:
- Extract only information present in the document.
- Never guess or invent values, dates, units, or page numbers.
- Never calculate derived values unless the document already states them.
- Preserve exact numeric values and units.
- Distinguish patient values from reference ranges.
- Preserve dates and page numbers when present.
- Return null when a field is unavailable.
- Do not interpret medical meaning.
- Do not diagnose.
- Return valid JSON only.

JSON shape:
{
  "document_type": string or null,
  "report_date": "YYYY-MM-DD" or null,
  "biomarkers": [
    {
      "name": string,
      "normalized_name": string,
      "original_field": string or null,
      "value": number or null,
      "unit": string or null,
      "reference_range": string or null,
      "reference_low": number or null,
      "reference_high": number or null,
      "flag": string or null,
      "source_page": number or null,
      "excerpt": string or null
    }
  ],
  "bio_ai_metrics": [
    {
      "name": string,
      "normalized_name": string,
      "value": number or null,
      "unit": string or null,
      "source_page": number or null
    }
  ]
}
"""


def _pages_from_chunks(chunks: list[Any]) -> str:
    parts: list[str] = []
    total = 0
    for chunk in chunks:
        page = getattr(chunk, "page_start", None)
        text = (getattr(chunk, "text", None) or "")[:4000]
        block = f"[page {page}]\n{text}"
        if total + len(block) > 24000:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def extract_structured_with_llm(document_id: str, chunks: list[Any]) -> ExtractedHealthDocument | None:
    if not settings.enable_llm:
        return None
    text = _pages_from_chunks(chunks)
    if not text.strip():
        return None
    messages = [
        {"role": "system", "content": EXTRACTION_INSTRUCTIONS},
        {
            "role": "user",
            "content": f"Document ID: {document_id}\nExtract structured health facts.\n\n{text}",
        },
    ]
    try:
        raw = get_llm_client().complete(messages, json_mode=True)
    except LLMUnavailableError:
        logger.warning("llm_pdf_extract_unavailable document_id=%s", document_id)
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("llm_pdf_extract_malformed document_id=%s", document_id)
        return None
    if not isinstance(payload, dict):
        return None
    try:
        biomarkers = []
        for item in payload.get("biomarkers") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("metric") or "").strip()
            if not name:
                continue
            normalized = primary_lab_key(str(item.get("normalized_name") or name)) or str(
                item.get("normalized_name") or name
            ).lower().replace(" ", "_")
            biomarkers.append(
                ExtractedBiomarker(
                    name=name or display_name_for(normalized),
                    normalized_name=normalized,
                    original_field=item.get("original_field") or item.get("metric"),
                    value=item.get("value"),
                    unit=item.get("unit"),
                    reference_range=item.get("reference_range"),
                    reference_low=item.get("reference_low"),
                    reference_high=item.get("reference_high"),
                    flag=item.get("flag"),
                    source_page=item.get("source_page") or item.get("page"),
                    excerpt=(item.get("excerpt") or None),
                    confidence="high" if item.get("value") is not None else "low",
                )
            )
        risks = []
        for item in payload.get("bio_ai_metrics") or []:
            if not isinstance(item, dict):
                continue
            risks.append(
                ExtractedRisk.model_validate(
                    {
                        "name": item.get("name"),
                        "normalized_name": item.get("normalized_name") or item.get("name"),
                        "value": item.get("value"),
                        "unit": item.get("unit"),
                        "source_page": item.get("source_page") or item.get("page"),
                    }
                )
            )
        return ExtractedHealthDocument(
            document_id=document_id,
            document_type=payload.get("document_type"),
            report_date=payload.get("report_date"),
            biomarkers=biomarkers,
            bio_ai_metrics=risks,
            extraction_method="llm",
            extracted_once=True,
        )
    except ValidationError:
        logger.warning("llm_pdf_extract_invalid_schema document_id=%s", document_id)
        return None
