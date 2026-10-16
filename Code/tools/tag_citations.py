"""
Insert "[CITE AS: <Law> - Art. N]" label lines above every article heading in a
regulations.txt file, so the LLM always knows which law an article belongs to.

The official legal text is left unchanged; only the label lines are added.
Re-running the script is safe: existing labels are removed and regenerated.

Usage:
    python Code/tools/tag_citations.py "Data/Regulations/Rental/Italy/regulations.txt"
"""
import re
import sys

# (regex that marks the start of a law's section, canonical short name)
# Short names match the ones already used in the Italy risky_clauses.txt files.
LAW_HEADERS = [
    (r"^LEGGE 9 dicembre 1998\s*,\s*n\. 431", "Legge 431/1998"),
    (r"^\(CODICE CIVILE", "Codice civile"),
    (r"^CODICE CIVILE", "Codice civile"),
    (r"^LEGGE 27 luglio 1978, n\. 392", "Legge 392/1978"),
    (r"^LEGGE 30 dicembre 2004, n\. 311", "Legge 311/2004"),
    (r"^DECRETO LEGISLATIVO 6 settembre 2005, n\. 206", "Codice del consumo"),
    (r"^COSTITUZIONE DELLA REPUBBLICA ITALIANA", "Costituzione"),
    (r"^LEGGE 15 luglio 1966, n\. 604", "Legge 604/1966"),
]

# "Art. 1", "Art. 4-bis", "Art. 1571.", "Art. 11 — Deposito cauzionale", "Art. 1, comma 346"
ARTICLE_HEADING = re.compile(r"^Art\.\s*(\d+(?:-bis|-ter)?)(\s*,\s*comma\s*\d+)?\.?(\s*[—-].*)?$")

NOTE = ("NOTE: Lines beginning with [CITE AS: ...] are editorial citation labels added by "
        "ContractNerd. All other legal text is unchanged from the official source.")


def tag(text):
    out, current_law = [], None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[CITE AS:") or stripped == NOTE:
            continue  # drop old labels so the script can be re-run
        for pattern, name in LAW_HEADERS:
            if re.match(pattern, stripped):
                current_law = name
                break
        m = ARTICLE_HEADING.match(stripped)
        if m and current_law:
            art = m.group(1) + (m.group(2) or "")
            out.append(f"[CITE AS: {current_law} - Art. {art.strip()}]")
        out.append(line)
    return NOTE + "\n\n" + "\n".join(out) + "\n"


if __name__ == "__main__":
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            original = f.read()
        tagged = tag(original)
        with open(path, "w", encoding="utf-8") as f:
            f.write(tagged)
        labels = [l for l in tagged.splitlines() if l.startswith("[CITE AS:")]
        print(f"{path}: {len(labels)} labels")
