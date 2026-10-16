"""
Live check of Italy citations. Runs the real pipeline (needs OPENAI_API_KEY in .env)
and reports every Legal Authority the model cites, plus any that fail the
citation check.

Run from the repo root:
    python Code/tools/test_italy_citations.py uploads/italy_lease_allegatoA_3plus2.pdf Rental
    python Code/tools/test_italy_citations.py path/to/italy_employment.pdf Employment
"""
import os
import re
import sys

sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()

from Code.base.clause_comparison import clause_comparison
from Code.base.utils.citations import load_labels, check_authority

pdf, contract_type = sys.argv[1], sys.argv[2]
regs = os.path.join("Data", "Regulations", contract_type, "Italy", "regulations.txt")
risky = os.path.join("Data", "Risky Clauses", contract_type, "Italy", "risky_clauses.txt")

output = clause_comparison(
    contract_path=pdf, law_path=regs, risky_clauses=risky,
    model=os.environ.get("LLM_MODEL", "gpt-4o-mini"), role="user",
    api_base=os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
    api_key=os.environ["OPENAI_API_KEY"], temperature=0, top_p=0.1, max_tokens=8192,
)

labels = load_labels(open(regs, encoding="utf-8").read())
cited, bad = 0, 0
for line in output.splitlines():
    m = re.match(r"^[\*\-#\s]*Legal Authority:?\**\s*(.+)$", line.strip(), re.I)
    if not m or m.group(1).strip().lower() in ("none", "n/a"):
        continue
    cited += 1
    problems = check_authority(m.group(1), labels)
    bad += bool(problems)
    print(("FAIL " if problems else "ok   ") + m.group(1) + (f"  -> {problems}" if problems else ""))

print(f"\n{cited} citations, {bad} failed the check")
with open("italy_citation_test_output.txt", "w", encoding="utf-8") as f:
    f.write(output)
print("Full model output saved to italy_citation_test_output.txt (review the explanations by hand too).")
