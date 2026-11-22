# France – Rental: regulations (not added yet)

Put the law text here as `regulations.txt`. Until that file exists, the app stops with "France is not set up yet". Once it exists, France works like Italy (the risky-clause file is optional).

Steps:
1. Copy each law word for word from an official source, in the original language, into `regulations.txt`. Official source for France: Légifrance (https://www.legifrance.gouv.fr). Keep each law's title line and each article heading as printed (e.g. "Article 3").
2. In `Code/tools/tag_citations.py`, add one line per law to `LAW_HEADERS["France"]`: a pattern matching the law's title line, and the short name to use in labels.
3. In `Code/base/utils/citations.py`, add the same short name to `LAW_ALIASES`, with the ways the model may write it.
4. Add the labels: `python Code/tools/tag_citations.py "Data/Regulations/Rental/France/regulations.txt"`. If it prints a WARNING, a law title is missing from step 2.
5. Test: `python Code/tools/test_citations.py <contract.pdf> Rental France`, or run it on the site.

Do not paraphrase or summarise the law.
