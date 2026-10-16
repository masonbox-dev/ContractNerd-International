import os
import re
import openai

from Code.base.utils.functions import read_document, extract_info


def clause_comparison(
    contract_path,
    law_path,
    risky_clauses,
    model,
    role,
    api_base,
    api_key,
    temperature,
    top_p,
    max_tokens,
    retries=5,
):
    """Run source-grounded clause analysis."""
    client = openai.OpenAI(api_key=api_key, base_url=api_base)

    def call_llm(prompt: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": role, "content": prompt}],
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def law_comparison(contract: str, laws: str) -> str:
        prompt = f"""
You are a source-grounded contract reviewer.

Analyze every contract clause individually against the provided jurisdiction-specific legal reference.
This is an academic issue-spotting tool, not legal advice.

Critical rules:
1. Use the exact clause text from the contract. Each clause below starts with an ID in square brackets, such as [C3]. Do not copy the ID into the clause text.
2. Do not invent Acts, sections, cases, rules, legal duties, or legal requirements.
3. A legal authority may be cited only if it appears in the provided legal reference. If the reference contains labels such as "[CITE AS: Codice civile - Art. 1590]", copy the Legal Authority from the label directly above the provision you relied on (you may add a paragraph or letter, e.g. "Art. 13(1)"). The provision you cite must itself contain the requirement you describe. Never pair a law name with an article number taken from a different law. If the reference has no provision on the clause's subject, use Legal Authority: None, even when the contract text itself names a law or article.
4. If the contract has blanks or placeholders such as "(Date)", "(Amount)", "(Address)", "(Starting Date of Agreement)", "(Expiry Date of Agreement)", "(Amount of rent in Numbers)", or "(city)", classify that as Missing Required Information or Ambiguous. Do not cite a statute or call it non-compliant only because the field is blank. Cite a statute only when the actual clause text conflicts with a specific legal requirement in the provided reference.
5. Distinguish these categories carefully: legal non-compliance, missing required information, ambiguity, practical risk, unfairness, and ordinary low-risk drafting.
6. Do not flag a clause as non-compliant based on a hypothetical fact that contradicts the clause.
7. When applicability depends on facts not present in the contract, say "Applicability uncertain" and explain what fact is missing.
8. For every possible legal issue, explain exactly which legal source applies, what that source requires, and what part of the clause conflicts with it. If the issue is only missing dates, missing rent amount, missing address, missing city, or another blank placeholder, use Legal Authority: None unless the legal reference directly requires that exact missing field.
9. Respond in English.
10. Do not provide legal advice. Provide academic issue spotting only.
11. Return an entry for every clause ID in the list. Do not skip any ID, even if the clause looks standard.

Return exactly this format for every clause:

Clause: "[EXACT FULL CLAUSE TEXT]"
Clause ID: [The ID from the list, e.g. C3]
Legal Authority: [Exact Act and section from the reference, or "None"]
Preliminary Legal Finding: [Compliant / Missing Information / Ambiguous / Practical Risk / Potentially Non-Compliant / Applicability Uncertain]
Reasoning: [Concise explanation comparing the clause to the cited source. If no source applies, explain the drafting issue without calling it illegal.]

Contract Clauses:
{contract}

Jurisdiction-Specific Legal Reference:
{laws}
"""
        return call_llm(prompt)

    def classify_risk(source_backed_analysis: str, risk_guidance: str) -> str:
        prompt = f"""
You are converting source-backed contract analysis into the final UI output.
Respond in English.

Use the source-backed analysis below:

{source_backed_analysis}

Assign one classification and one risk tier to every clause.

Allowed classifications:
- Enforceable
- Missing Required Information
- Ambiguous
- Potentially Prejudicial
- Potentially Unenforceable
- Requires Further Legal Review

Allowed risk tiers:
- High Risk
- Medium Risk
- Low Risk

Rules:
1. Preserve the exact clause text.
2. Do not invent legal authorities.
3. Use "Legal Authority: None" unless the authority is expressly cited in the source-backed analysis. Copy each clause's Legal Authority exactly from the source-backed analysis for that same clause. The risk guidance below explains how to classify; it is not a source of citations, so never replace, add or renumber an authority based on it.
4. Treat unresolved placeholders as Missing Required Information, not as legal violations.
5. Use High Risk only for a clause that the source-backed analysis identifies as potentially non-compliant or potentially unenforceable with a cited legal authority, or for a serious rights-remedy issue requiring legal review.
6. Use Medium Risk for missing information, ambiguity, practical risk, or potentially prejudicial wording.
7. Use Low Risk for standard clauses that are clear and not flagged by the legal reference.
8. For each flagged clause, state: the law or absence of law, what is wrong or missing, and how to fix it.
9. If a clause says the agreement will be registered, do not describe it as saying registration is unnecessary.
10. This is academic issue spotting, not legal advice.
11. Keep every clause's Clause ID exactly as given, and return every clause from the analysis. Do not skip any.

Additional risk guidance:
{risk_guidance}

Return exactly this format for every clause:

Clause: "[EXACT FULL CLAUSE TEXT]"
Clause ID: [Same ID as in the analysis, e.g. C3]
Legal Authority: [Exact Act and section, or "None"]
Classification: [One allowed classification]
Risk Tier: [High Risk / Medium Risk / Low Risk]
Explanation: [Source-backed explanation. If this is not a legal violation, say it is a drafting or practical issue.]
Improvement Guidance: [Specific revision or review step]
"""
        return call_llm(prompt)

    contract_text = read_document(contract_path)
    regulations_text = read_document(law_path)

    if risky_clauses and os.path.exists(risky_clauses):
        risk_guidance_text = read_document(risky_clauses)
    else:
        risk_guidance_text = ""

    # Give every clause an ID (C1, C2, ...) so we can check that each one comes back.
    clause_list = [c for c in extract_info(contract_text=contract_text).split("\n") if c.strip()]
    items = [(f"C{i}", text) for i, text in enumerate(clause_list, 1)]

    def analyze(batch):
        numbered = "\n".join(f"[{cid}] {text}" for cid, text in batch)
        source_backed = law_comparison(numbered, regulations_text)
        return classify_risk(source_backed, risk_guidance_text)

    def find_missing(output, batch):
        returned_ids = set(re.findall(r"Clause ID:\**\s*\[?(C\d+)\]?", output, re.I))
        flat_output = " ".join(output.split())
        missing = []
        for cid, text in batch:
            if cid in returned_ids:
                continue
            # Also count it as returned if its text appears (in case the model left out the ID).
            snippet = " ".join(text.split())[:60]
            if snippet and snippet in flat_output:
                continue
            missing.append((cid, text))
        return missing

    final_output = analyze(items)

    # One retry, sending only the clauses that did not come back.
    missing = find_missing(final_output, items)
    if missing:
        print(f"Retrying {len(missing)} missing clause(s): {[cid for cid, _ in missing]}")
        final_output += "\n\n" + analyze(missing)
        missing = find_missing(final_output, items)

    # Anything still missing is shown as "Not Analyzed" instead of silently disappearing.
    for cid, text in missing:
        print(f"Clause {cid} still missing after one retry; marking as Not Analyzed")
        final_output += (
            f'\n\nClause: "{text}"\n'
            f"Clause ID: {cid}\n"
            "Legal Authority: None\n"
            "Classification: Not Analyzed\n"
            "Risk Tier: Not Analyzed\n"
            "Explanation: This clause was not returned by the analysis, even after one retry.\n"
            "Improvement Guidance: Rerun the analysis or review this clause manually.\n"
        )

    return final_output

if __name__ == "__main__":
    final_evaluation = clause_comparison(
        contract_path="example_contract.pdf",
        law_path="example_regulations.txt",
        risky_clauses="example_risk_guidance.txt",
        model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        role="user",
        api_key=os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY_HERE"),
        api_base=os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
        temperature=0.3,
        top_p=0.1,
        max_tokens=8192,
    )
    print(final_evaluation)