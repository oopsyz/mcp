"""Build a canonical TMF API catalog for registry-agent validation.

This script reads the API specs under ``../vector_service/data/api_yaml`` and
``../vector_service/data/api_json`` and produces:

- ``registry_agent/data/tmf_api_catalog.json``: canonical machine-readable data
- ``tmf_api_catalog.md``: human-readable summary table
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT.parent / "vector_service" / "data"
YAML_DIR = SOURCE_ROOT / "api_yaml"
JSON_DIR = SOURCE_ROOT / "api_json"

CATALOG_JSON = ROOT / "registry_agent" / "data" / "tmf_api_catalog.json"
CATALOG_MD = ROOT / "tmf_api_catalog.md"


def _parse_version(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version or "")
    return tuple(int(part) for part in parts) if parts else (0,)


def _strip_quotes(value: str) -> str:
    return value.strip().strip("'").strip('"')


def _extract_yaml_info(text: str) -> dict[str, str]:
    lines = text.splitlines()
    in_info = False
    title = ""
    version = ""
    desc = ""
    collecting_desc = False
    desc_indent: int | None = None
    desc_lines: list[str] = []

    for line in lines:
        if not in_info:
            if line.strip() == "info:":
                in_info = True
            continue

        if line and not line.startswith((" ", "\t")):
            break

        if not title:
            match = re.match(r"^\s{2}title:\s*(.*)$", line)
            if match:
                title = _strip_quotes(match.group(1))
                continue

        if not version:
            match = re.match(r"^\s{2}version:\s*(.*)$", line)
            if match:
                version = _strip_quotes(match.group(1))
                continue

        if not collecting_desc:
            match = re.match(r"^\s{2}description:\s*(.*)$", line)
            if match:
                value = match.group(1).strip()
                if value in {">", ">-", ">+", "|", "|-", "|+"}:
                    collecting_desc = True
                    continue
                desc = _strip_quotes(value)
                continue
        else:
            if desc_indent is None:
                if not line.strip():
                    continue
                desc_indent = len(line) - len(line.lstrip(" "))

            if not line.strip():
                desc_lines.append("")
                continue

            indent = len(line) - len(line.lstrip(" "))
            if indent < desc_indent:
                break
            desc_lines.append(line[desc_indent:])

    if desc_lines:
        desc = "\n".join(desc_lines)

    return {"title": title, "version": version, "description": desc}


def _clean_name(raw: str, api_id: str) -> str:
    name = raw.strip() or api_id
    name = re.sub(r"^TMF\s*-\s*\d+\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^TMF\d+\s*[-:]\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^TMF\s*API\s*Reference\s*:?\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+API$", "", name, flags=re.IGNORECASE)
    return name.strip(" :-") or api_id


def _extract_json_info(text: str) -> dict[str, str]:
    obj = json.loads(text)
    info = obj.get("info") or {}
    return {
        "title": str(info.get("title", "")).strip(),
        "version": str(info.get("version", "")).strip(),
        "description": str(info.get("description", "")).strip(),
    }


def _clean_summary(raw: str, fallback: str) -> str:
    if not raw:
        return fallback

    lines = raw.replace("\r", "").split("\n")
    kept: list[str] = []
    started = False

    for line in lines:
        text = line.strip()
        if not text:
            if started:
                break
            continue

        if not started:
            if text.startswith("##") or text.startswith("###"):
                continue
            if re.match(r"^TMF\s*API\s*Reference", text, re.IGNORECASE):
                continue
            if re.match(r"^Test\s+TMF\s*API\s*Reference", text, re.IGNORECASE):
                continue
            if re.match(r"^TMF\d+\s*[-:]", text, re.IGNORECASE):
                continue
            if re.match(r"^Release\s*:", text, re.IGNORECASE):
                continue
            if re.match(r"^Version\s+\d", text, re.IGNORECASE):
                continue
            if re.match(
                r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$",
                text,
                re.IGNORECASE,
            ):
                continue
            if re.match(r"^(This is )?Swagger UI environment generated", text, re.IGNORECASE):
                continue
            if re.match(r"^My api short documentation$", text, re.IGNORECASE):
                continue
            started = True

        if text.startswith("##") or text.startswith("###"):
            break
        if text.startswith("- ") or text.startswith("* "):
            break
        if re.match(r"^Copyright\b", text, re.IGNORECASE):
            break

        kept.append(text)

    summary = " ".join(kept)
    summary = re.sub(r"\s+", " ", summary).strip()
    summary = summary.replace("**", "")
    summary = summary.replace("\\n", " ")
    summary = re.sub(r"^TMF\d+\s*[-:]\s*", "", summary, flags=re.IGNORECASE)
    summary = re.sub(r"^TMF\s*-\s*\d+\s+", "", summary, flags=re.IGNORECASE)
    summary = re.sub(r"^TMF\s*API\s*Reference\s*:?\s*", "", summary, flags=re.IGNORECASE)
    summary = re.sub(r"^Test\s+TMF\s*API\s*Reference\s*:?\s*", "", summary, flags=re.IGNORECASE)
    summary = re.sub(r"^Release\s*:\s*[^-]+-\s*", "", summary, flags=re.IGNORECASE)
    summary = re.sub(r"^Version\s+\d+(?:\.\d+)*\s*", "", summary, flags=re.IGNORECASE)
    summary = re.split(r"\b(?:API performs the following operations|Operations for|Notification of events|Copyright)\b", summary, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    sentences = re.split(r"(?<=[.!?])\s+", summary)
    if len(sentences) > 2:
        summary = " ".join(sentences[:2]).strip()
    summary = summary.strip(" :.-")
    return summary or fallback


def _derive_keywords(api_id: str, name: str, summary: str) -> list[str]:
    base_terms = {api_id.lower(), name.lower()}
    normalized_name = name.replace("-", " ")
    name_words = [word for word in re.findall(r"[a-z0-9]+", normalized_name.lower()) if word not in {"api", "management"}]
    for word in name_words:
        if len(word) >= 4:
            base_terms.add(word)
    for idx in range(len(name_words) - 1):
        phrase = f"{name_words[idx]} {name_words[idx + 1]}"
        if len(phrase) <= 40:
            base_terms.add(phrase)

    first_sentence = re.split(r"(?<=[.!?])\s+", summary.strip())[0]
    signal_words = [
        word
        for word in re.findall(r"[a-z0-9]+", first_sentence.lower())
        if word not in {"this", "that", "with", "from", "into", "used", "allows", "allow", "provides", "provide", "standardized", "mechanism", "management", "api"}
        and len(word) >= 5
    ]
    for word in signal_words[:8]:
        base_terms.add(word)

    result = sorted(term for term in base_terms if term and len(term) <= 40)
    return result[:20]


def _choose_entry(existing: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if existing is None:
        return candidate

    existing_key = (_parse_version(existing["version"]), existing["source_format"] == "yaml")
    candidate_key = (_parse_version(candidate["version"]), candidate["source_format"] == "yaml")
    return candidate if candidate_key >= existing_key else existing


def build_catalog() -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}

    for source_dir, source_format in ((YAML_DIR, "yaml"), (JSON_DIR, "json")):
        for path in sorted(source_dir.glob("*")):
            match = re.match(r"^(TMF\d+)", path.name)
            if not match:
                continue

            api_id = match.group(1)
            text = path.read_text(encoding="utf-8", errors="ignore")
            info = _extract_yaml_info(text) if source_format == "yaml" else _extract_json_info(text)

            name = _clean_name(info["title"], api_id)
            summary = _clean_summary(info["description"], name)

            candidate = {
                "id": api_id,
                "name": name,
                "summary": summary,
                "version": info["version"].strip(),
                "source_format": source_format,
                "source_file": str(path.resolve()),
                "keywords": _derive_keywords(api_id, name, summary),
            }
            chosen[api_id] = _choose_entry(chosen.get(api_id), candidate)

    return [chosen[key] for key in sorted(chosen.keys(), key=lambda value: int(value[3:]))]


def write_catalog_json(entries: list[dict[str, Any]]) -> None:
    payload = {
        "generated_from": str(SOURCE_ROOT.resolve()),
        "total": len(entries),
        "apis": entries,
    }
    CATALOG_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_catalog_md(entries: list[dict[str, Any]]) -> None:
    lines = [
        f"# TMF API Catalog ({len(entries)} APIs)",
        "",
        "TMF ID | Name | Description",
        "-------|------|-------------",
    ]
    for entry in entries:
        description = entry["summary"].replace("\n", " ").replace("|", "\\|")
        lines.append(f'{entry["id"]} | {entry["name"]} | {description}')
    CATALOG_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    entries = build_catalog()
    write_catalog_json(entries)
    write_catalog_md(entries)
    print(f"Built TMF catalog with {len(entries)} APIs")


if __name__ == "__main__":
    main()
