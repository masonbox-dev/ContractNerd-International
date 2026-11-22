"""
Live check of citations for any jurisdiction. Runs the real pipeline (needs OPENAI_API_KEY
in .env) and reports every Legal Authority the model cites, plus any that fail the
citation check. Same as test_italy_citations.py, with the country as an argument.

Run from the repo root:
    python Code/tools/test_citations.py path/to/contract.pdf Rental France
    python Code/tools/test_citations.py path/to/contract.pdf Employment Germany
    python Code/tools/test_citations.py uploads/italy_lease_allegatoA_3plus2.pdf Rental Italy
"""
import os
import re
import sys

sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()

from Code.base.clause_comparison import clause_comparison
from Code.base.utils.citations import load_labels, check_authority

if len(sys.argv) != 4:
    sys.exit("Usage: python Code/tools/test_citations.py <contract.pdf> <Rental|Employment> <Country>")
pdf, contract_type, country = sys.argv[1], sys.argv[2], sys.argv[3]

regs = os.path.join("Data", "Regulations", contract_type, country, "regulations.txt")
risky = os.path.join("Data", "Risky Clauses", contract_type, country, "risky_clauses.txt")
if not os.path.exists(regs):
    sys.exit(f"{country} is not set up yet: no law file at {regs}")
if not os.path.exists(risky):
    print(f"Note: no risky-clause file at {risky}; running without risk guidance.")
    risky = ""

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
    problems = check_authority(m.group(1), labels, country)
    bad += bool(problems)
    print(("FAIL " if problems else "ok   ") + m.group(1) + (f"  -> {problems}" if problems else ""))

print(f"\nModel: {os.environ.get('LLM_MODEL', 'gpt-4o-mini')}")
print(f"{cited} citations, {bad} failed the check")
out_name = f"{country.lower().replace(' ', '_')}_citation_test_output.txt"
with open(out_name, "w", encoding="utf-8") as f:
    f.write(output)
print(f"Full model output saved to {out_name} (review the explanations by hand too).")
