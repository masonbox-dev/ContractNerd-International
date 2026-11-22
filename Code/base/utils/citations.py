"""
Deterministic check that a cited legal authority actually exists in the
jurisdiction's regulations file, with the article attached to the right law.

Only runs for reference files that contain "[CITE AS: <Law> - Art. N]" labels
(see Code/tools/tag_citations.py). Other jurisdictions are left untouched.
"""
import re

# "Art. N" for Italy, France, Spain; "§ N" for Germany.
LABEL = re.compile(r"^\[CITE AS:\s*(.+?)\s+-\s+(?:Art\.|§)\s*([0-9]+[a-z]?(?:-bis|-ter|\s(?:bis|ter))?)", re.M)

# Ways the model may write each law's name (lower-case regex fragments).
LAW_ALIASES = {
    "Legge 431/1998": r"431",
    "Legge 392/1978": r"392",
    "Legge 311/2004": r"311",
    "Legge 604/1966": r"604",
    "Codice civile": r"codice civile|civil code|c\.c\.",
    "Codice del consumo": r"codice del consumo|consumer code|206/2005",
    "Costituzione": r"costituzione|constitution",
    # France: add "<short name used in labels>": r"<ways the model may write it>" for each law added.
    # Spain: same.
    # Germany: same.
}

ART_REF = re.compile(r"\barts?\.?\s*([0-9]+(?:-bis|-ter)?)(?:\s*[-–]\s*([0-9]+))?", re.I)

# How an article is written in a citation, for countries that do not use "Art." only.
# Italy and the other jurisdictions keep ART_REF above.
ART_REF_BY_COUNTRY = {
    # "Art. 3", "article 3", "articles 3 à 5", "article 3 bis"
    "France": re.compile(r"\b(?:arts?\.?|articles?)\s*([0-9]+(?:\s(?:bis|ter))?)(?:\s*(?:à|[-–])\s*([0-9]+))?", re.I),
    # "Art. 9", "artículo 9", "artículos 9 a 11", "artículo 4 bis"
    "Spain": re.compile(r"\b(?:arts?\.?|art[íi]culos?)\s*([0-9]+(?:\s(?:bis|ter))?)(?:\s*(?:a|[-–])\s*([0-9]+))?", re.I),
    # "§ 535", "§§ 535-537", "§ 556d"
    "Germany": re.compile(r"(?:§§?|\bparagraph)\s*([0-9]+[a-z]?)(?:\s*[-–]\s*([0-9]+))?", re.I),
}


def load_labels(regulations_text):
    """Return {law_name: {article, ...}} from the [CITE AS: ...] labels."""
    labels = {}
    for law, art in LABEL.findall(regulations_text or ""):
        labels.setdefault(law, set()).add(art)
    return labels


def check_authority(authority, labels, jurisdiction=None):
    """
    Return a list of problems with the cited authority (empty list = OK).
    Each article number is matched to the closest law name written before it.
    jurisdiction picks how articles are written (France, Spain, Germany); others use ART_REF.
    """
    art_ref = ART_REF_BY_COUNTRY.get(jurisdiction, ART_REF)
    art_word = "§" if jurisdiction == "Germany" else "Art."
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
    for m in art_ref.finditer(text):
        start, end = m.group(1), m.group(2)
        articles = [start]
        if end and start.isdigit() and int(end) > int(start) and int(end) - int(start) < 20:
            articles = [str(n) for n in range(int(start), int(end) + 1)]
        preceding = [law for pos, law in mentions if pos < m.start()]
        law = preceding[-1] if preceding else None
        for art in articles:
            if law is None:
                if not any(art in arts for arts in labels.values()):
                    problems.append(f"{art_word} {art} is not in the reference")
                else:
                    problems.append(f"{art_word} {art} cited without naming its law")
            elif art not in labels[law]:
                owners = [l for l, arts in labels.items() if art in arts]
                hint = (f" (the reference only has {art_word} {art} under {', '.join(owners)}; check whether that law covers this topic)" if owners else "")
                problems.append(f"{law} - {art_word} {art} is not in the reference{hint}")
    if not problems and not art_ref.search(text):
        problems.append("no article number found in the citation")
    return problems
