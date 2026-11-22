"""
Insert "[CITE AS: <Law> - Art. N]" label lines above every article heading in a
regulations.txt file, so the LLM always knows which law an article belongs to.
(German files get "[CITE AS: <Law> - § N]".)

The official legal text is left unchanged; only the label lines are added.
Re-running the script is safe: existing labels are removed and regenerated.

The country is taken from the file's folder (Data/Regulations/<type>/<Country>/).

Usage:
    python Code/tools/tag_citations.py "Data/Regulations/Rental/Italy/regulations.txt"
    python Code/tools/tag_citations.py "Data/Regulations/Rental/France/regulations.txt"

Adding a new law: put a line in LAW_HEADERS for that country, with a pattern that
matches the law's title line exactly as it appears in the pasted official text, and
the short name to use in labels. Then add the same short name to LAW_ALIASES in
Code/base/utils/citations.py.
"""
import os
import re
import sys

# For each country: (regex that marks the start of a law's section, canonical short name).
LAW_HEADERS = {
    # Short names match the ones already used in the Italy risky_clauses.txt files.
    "Italy": [
        (r"^LEGGE 9 dicembre 1998\s*,\s*n\. 431", "Legge 431/1998"),
        (r"^\(CODICE CIVILE", "Codice civile"),
        (r"^CODICE CIVILE", "Codice civile"),
        (r"^LEGGE 27 luglio 1978, n\. 392", "Legge 392/1978"),
        (r"^LEGGE 30 dicembre 2004, n\. 311", "Legge 311/2004"),
        (r"^DECRETO LEGISLATIVO 6 settembre 2005, n\. 206", "Codice del consumo"),
        (r"^COSTITUZIONE DELLA REPUBBLICA ITALIANA", "Costituzione"),
        (r"^LEGGE 15 luglio 1966, n\. 604", "Legge 604/1966"),
    ],
    # Add each law's title line and short name when its text is pasted in (source: Légifrance).
    "France": [],
    # Add each law's title line and short name when its text is pasted in (source: BOE).
    "Spain": [],
    # Add each law's title line and short name when its text is pasted in (source: gesetze-im-internet.de).
    "Germany": [],
}

# How an article heading line looks in each country's official texts.
# Group "art" is the article number; "extra" (Italy only) is a ", comma N" part.
ARTICLE_HEADINGS = {
    # "Art. 1", "Art. 4-bis", "Art. 1571.", "Art. 11 — Deposito cauzionale", "Art. 1, comma 346"
    "Italy": re.compile(r"^Art\.\s*(?P<art>\d+(?:-bis|-ter)?)(?P<extra>\s*,\s*comma\s*\d+)?\.?(\s*[—-].*)?$"),
    # "Article 3", "Article 3 bis", "Article 1709"
    "France": re.compile(r"^Article\s+(?P<art>\d+(?:\s(?:bis|ter))?)\b"),
    # "Artículo 9.", "Artículo 36. Fianza.", "Artículo 4 bis"
    "Spain": re.compile(r"^Art[íi]culo\s+(?P<art>\d+(?:\s(?:bis|ter))?)\b"),
    # "§ 535 Inhalt und Hauptpflichten des Mietvertrags", "§ 556d"
    "Germany": re.compile(r"^§\s*(?P<art>\d+[a-z]?)\b"),
}

# Germany cites "§ 535"; everyone else "Art. N".
ARTICLE_PREFIX = {"Germany": "§"}

NOTE = ("NOTE: Lines beginning with [CITE AS: ...] are editorial citation labels added by "
        "ContractNerd. All other legal text is unchanged from the official source.")


def country_from_path(path):
    """Data/Regulations/<type>/<Country>/regulations.txt -> <Country> (default Italy)."""
    parts = os.path.normpath(path).split(os.sep)
    for country in LAW_HEADERS:
        if country in parts:
            return country
    return "Italy"


def tag(text, country="Italy", unlabelled=None):
    """Return text with labels. Article headings found before any known law header
    are counted in unlabelled[0] (when a list is passed) instead of being labelled."""
    headers = LAW_HEADERS[country]
    heading = ARTICLE_HEADINGS[country]
    prefix = ARTICLE_PREFIX.get(country, "Art.")
    out, current_law = [], None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[CITE AS:") or stripped == NOTE:
            continue  # drop old labels so the script can be re-run
        for pattern, name in headers:
            if re.match(pattern, stripped):
                current_law = name
                break
        m = heading.match(stripped)
        if m and current_law:
            art = m.group("art") + ((m.groupdict().get("extra")) or "")
            out.append(f"[CITE AS: {current_law} - {prefix} {art.strip()}]")
        elif m and unlabelled is not None:
            unlabelled[0] += 1
        out.append(line)
    return NOTE + "\n\n" + "\n".join(out) + "\n"


if __name__ == "__main__":
    for path in sys.argv[1:]:
        country = country_from_path(path)
        with open(path, encoding="utf-8") as f:
            original = f.read()
        unlabelled = [0]
        tagged = tag(original, country, unlabelled)
        with open(path, "w", encoding="utf-8") as f:
            f.write(tagged)
        labels = [l for l in tagged.splitlines() if l.startswith("[CITE AS:")]
        print(f"{path} ({country}): {len(labels)} labels")
        if unlabelled[0]:
            print(f"  WARNING: {unlabelled[0]} article headings got no label because no law title "
                  f"above them is listed in LAW_HEADERS['{country}']. Add the law's title line there.")
