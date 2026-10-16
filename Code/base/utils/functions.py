from pathlib import Path
import fitz
import re

from pathlib import Path

import fitz


def read_document(file_path: str) -> str:
    """
    Read supported PDF or plain-text files and return their text.
    """
    if not file_path:
        raise ValueError("A file path is required.")

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        text_parts: list[str] = []

        with fitz.open(path) as pdf:
            for page in pdf:
                text_parts.append(page.get_text())

        return "\n".join(text_parts).strip()

    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8").strip()

    raise ValueError(f"Unsupported file type: {suffix}")

def extract_info(document, prompt, client, model, role, temperature, top_p, max_tokens):
    """
    Extracts information from the given document using the specified LLM model.
    """
    response = client.chat.completions.create(
        model       = model,
        messages    = [{"role": role,
                        "content": f"{prompt}: {document}"}],
        temperature = temperature,
        top_p       = top_p,
        max_tokens  = max_tokens,
    )

    # Collect streamed output into a single variable
    text = response.choices[0].message.content

    return (text)

def extract_info(contract_text):
    """
    Extracts clauses with subpoints combined into their main numbered clauses.
    Returns them as a numbered string with each main clause (including subpoints) on one line.
    """
    # Split the text into main sections using Arabic numbers or Chinese numbers/formats
    # e.g., "1.", "1、", "一、", "（一）", "第一条", "第1条", "Articolo 1" (Italian article headings)
    # The previous regex missed the simple '\d+\.' because of the non-capturing group structure.
    pattern = r'(?=\n(?:(?:\d+[\.、])|(?:[一二三四五六七八九十百千万]+[\.、])|(?:（[一二三四五六七八九十百千万]+）)|(?:\([0-9]+\))|(?:第[一二三四五六七八九十百千万0-9]+[章节条])|(?:(?:Articolo|ARTICOLO)\s*\d+\b)))'
    main_sections = re.split(pattern, contract_text.strip())

    # Sometimes the very first section is just the title (e.g., "房屋租赁合同")
    # We want to keep it if it contains actual clause data, but usually we filter empty ones later.
    processed_clauses = []

    for section in main_sections:
        if not section.strip():
            continue

        # Remove leading/trailing whitespace
        section = section.strip()

        # Combine all lines in the section into one line
        combined = ' '.join(line.strip() for line in section.split('\n') if line.strip())

        # Clean up multiple spaces
        combined = ' '.join(combined.split())

        processed_clauses.append(combined)

    return '\n'.join(processed_clauses)