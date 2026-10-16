"""
Deterministic check that a cited legal authority actually exists in the
jurisdiction's regulations file, with the article attached to the right law.

Only runs for reference files that contain "[CITE AS: <Law> - Art. N]" labels
(see Code/tools/tag_citations.py). Other jurisdictions are left untouched.
"""
import re

LABEL = re.compile(r"^\[CITE AS:\s*(.+?)\s+-\s+Art\.\s*([0-9]+(?:-bis|-ter)?)", re.M)

# Ways the model may write each law's name (lower-case regex fragments).
LAW_ALIASES = {
    "Legge 431/1998": r"431",
    "Legge 392/1978": r"392",
    "Legge 311/2004": r"311",
    "Legge 604/1966": r"604",
    "Codice civile": r"codice civile|civil code|c\.c\.",
    "Codice del consumo": r"codice del consumo|consumer code|206/2005",
    "Costituzione": r"costituzione|constitution",
}

ART_REF = re.compile(r"\barts?\.?\s*([0-9]+(?:-bis|-ter)?)(?:\s*[-–]\s*([0-9]+))?", re.I)


def load_labels(regulations_text):
    """Return {law_name: {article, ...}} from the [CITE AS: ...] labels."""
    labels = {}
    for law, art in LABEL.findall(regulations_text or ""):
        labels.setdefault(law, set()).add(art)
    return labels


def check_authority(authority, labels):
    """
    Return a list of problems with the cited authority (empty list = OK).
    Each article number is matched to the closest law name written before it.
    """
    if not labels or not authority:
        return []
    text = authority.lower()

    # Where each known law is mentioned in the citation string.
    mentions = []
    for law, alias in LAW_ALIASES.items():
        if law in labels:
            for m in re.finditer(alias, text):
                mentions.append((m.start(), law))
    mentions.sort()

    problems = []
    for m in ART_REF.finditer(text):
        start, end = m.group(1), m.group(2)
        articles = [start]
        if end and start.isdigit() and int(end) > int(start) and int(end) - int(start) < 20:
            articles = [str(n) for n in range(int(start), int(end) + 1)]
        preceding = [law for pos, law in mentions if pos < m.start()]
        law = preceding[-1] if preceding else None
        for art in articles:
            if law is None:
                if not any(art in arts for arts in labels.values()):
                    problems.append(f"Art. {art} is not in the reference")
                else:
                    problems.append(f"Art. {art} cited without naming its law")
            elif art not in labels[law]:
                owners = [l for l, arts in labels.items() if art in arts]
                hint = (f" (the reference only has Art. {art} under {', '.join(owners)}; check whether that law covers this topic)" if owners else "")
                problems.append(f"{law} - Art. {art} is not in the reference{hint}")
    if not problems and not ART_REF.search(text):
        problems.append("no article number found in the citation")
    return problems
