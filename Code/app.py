import os
from dotenv import load_dotenv
load_dotenv()
import re
import sys
import time
import traceback
from datetime import datetime

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Code.base.clause_comparison import clause_comparison
from Code.base.utils.citations import load_labels, check_authority

app = Flask(__name__, template_folder='ui/templates')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Field labels the LLM is asked to output, mapped to where the UI stores them.
FIELD_NAMES = {
    'legal authority': 'regulations',
    'regulations': 'regulations',
    'regulation': 'regulations',
    'classification': 'classification',
    'risk tier': 'risk_tier',
    'explanation': 'explanation',
    'reasoning': 'explanation',
    'improvement guidance': 'improvement_guidance',
}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze an uploaded contract against the selected jurisdiction."""
    try:
        jurisdiction = request.form.get('jurisdiction')
        contract_type = request.form.get('contractType')
        contract_file = request.files.get('contract')

        if not jurisdiction or not contract_type:
            return jsonify({"error": "Please select both jurisdiction and contract type."}), 400

        if not contract_file or not allowed_file(contract_file.filename):
            return jsonify({"error": "Please upload a PDF contract."}), 400

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        contract_filename = secure_filename(contract_file.filename)
        contract_path = os.path.join(app.config['UPLOAD_FOLDER'], contract_filename)
        contract_file.save(contract_path)
        print(f"Processing contract: {contract_path}")

        legal_resources = {
            'regulations': os.path.join(
                project_root,
                'Data',
                'Regulations',
                contract_type,
                jurisdiction,
                'regulations.txt'
            ),
            'risky_clauses': os.path.join(
                project_root,
                'Data',
                'Risky Clauses',
                contract_type,
                jurisdiction,
                'risky_clauses.txt'
            ),
            'gold_standard': os.path.join(
                project_root,
                'Data',
                'Gold Standards',
                contract_type,
                jurisdiction,
                'gold_standard.txt'
            ),
        }

        if jurisdiction in ["India - Delhi", "England and Wales"]:
            if not os.path.exists(legal_resources['regulations']):
                return jsonify({
                    "error": (
                        f"No India - Delhi regulation file was found. "
                        f"Expected file: {legal_resources['regulations']}"
                    )
                }), 400

            if not os.path.exists(legal_resources['risky_clauses']):
                return jsonify({
                    "error": (
                        f"No India - Delhi risky-clause file was found. "
                        f"Expected file: {legal_resources['risky_clauses']}"
                    )
                }), 400

        else:
            if not os.path.exists(legal_resources['regulations']):
                legal_resources['regulations'] = legal_resources['gold_standard']

            if not os.path.exists(legal_resources['risky_clauses']):
                legal_resources['risky_clauses'] = ""

            if not os.path.exists(legal_resources['regulations']):
                return jsonify({
                    "error": (
                        f"No legal reference was found for {jurisdiction} / {contract_type}. "
                        f"Expected file: {legal_resources['gold_standard']}"
                    )
                }), 400

        analysis_start = time.time()

        final_evaluation = clause_comparison(
            contract_path=contract_path,
            law_path=legal_resources['regulations'],
            risky_clauses=legal_resources['risky_clauses'],
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            role="user",
            api_base=os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
            api_key=os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY_HERE"),
            temperature=0,  # 0 = most consistent answers between runs
            top_p=0.1,
            max_tokens=8192,
        )

        print(f"Analysis completed in {time.time() - analysis_start:.2f}s")

        clauses = []
        current_clause = None

        for line in final_evaluation.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Strip markdown markers (e.g. "**Legal Authority:**", "- Classification:") for field detection.
            header = re.sub(r'^[\*#\-\s]+', '', line).replace('**', '').strip()

            if header.lower().startswith('clause:') or line.startswith('### Clause'):
                if current_clause and current_clause['text']:
                    clauses.append(current_clause)

                current_clause = {
                    'number': len(clauses) + 1,
                    'text': '',
                    'classification': '',
                    'risk_tier': '',
                    'details': {
                        'regulations': '',
                        'explanation': '',
                        'improvement_guidance': '',
                    },
                    'current_field': 'text',
                }

                if ':' in header:
                    text_part = header.split(':', 1)[1].strip().strip('"').strip("'")
                    if text_part:
                        current_clause['text'] = text_part

            elif current_clause:
                is_new_field = False

                if ':' in header:
                    field_part, content_part = header.split(':', 1)
                    field_lower = field_part.strip().lower()
                    content_part = content_part.strip()
                    # Exact field names only. Substring matching ("law" in field_lower) let
                    # explanation lines such as "Applicable law: ..." overwrite the citation.
                    matched_field = FIELD_NAMES.get(field_lower)

                    if matched_field == 'classification':
                        current_clause['is_unenforceable'] = (
                            'unenforceable' in content_part.lower()
                        )

                    if matched_field:
                        is_new_field = True
                        current_clause['current_field'] = matched_field

                        if matched_field in ['classification', 'risk_tier']:
                            current_clause[matched_field] = content_part
                        else:
                            current_clause['details'][matched_field] = content_part

                if not is_new_field:
                    curr_field = current_clause.get('current_field')

                    if curr_field == 'text' and not current_clause['text']:
                        current_clause['text'] = line.strip('"').strip("'")

                    elif curr_field in ['classification', 'risk_tier']:
                        current_clause[curr_field] = (
                            current_clause[curr_field] + ' ' + line
                        ).strip()

                    elif curr_field in current_clause['details']:
                        existing = current_clause['details'][curr_field]
                        separator = '<br>' if existing else ''
                        current_clause['details'][curr_field] = existing + separator + line

        if current_clause and current_clause.get('text'):
            clauses.append(current_clause)

        with open(legal_resources['regulations'], encoding='utf-8', errors='ignore') as f:
            citation_labels = load_labels(f.read()) if legal_resources['regulations'].endswith('.txt') else {}

        for c in clauses:
            authority = c['details'].get('regulations', '')
            authority = re.sub(
                r'^(?:\d+[\.\s]+|\([0-9]+\)\s*)',
                '',
                authority
            ).strip()

            if authority.lower() in ['none', 'not applicable', 'n/a']:
                authority = ''

            # Flag citations whose law/article pair is not in the reference file.
            problems = check_authority(authority, citation_labels)
            if problems:
                print(f"CITATION CHECK clause {c['number']}: {authority!r} -> {problems}")
                authority += ' [Unverified citation: ' + '; '.join(problems) + ']'

            c['details']['regulations'] = authority

        flagged_count = sum(
            1
            for c in clauses
            if c.get('risk_tier')
            and any(r in c['risk_tier'].lower() for r in ['high', 'medium'])
        )

        analysis_metadata = {
            'jurisdiction': jurisdiction,
            'contract_type': contract_type,
            'timestamp': datetime.now().isoformat(),
            'clause_count': len(clauses),
            'unenforceable_count': flagged_count,
        }

        print("DEBUG: Extracted clauses ->", analysis_metadata)

        return jsonify({
            "metadata": analysis_metadata,
            "clauses": clauses,
            "raw": final_evaluation,
            "legal_resources": legal_resources,
        })

    except Exception as e:
        app.logger.error(f"Analysis error: {str(e)}", exc_info=True)

        err_str = str(e)
        user_msg = "Analysis failed."

        if "429" in err_str or "rate limit" in err_str.lower():
            user_msg = "API rate limit exceeded. Please wait a few minutes and try again."

        elif "401" in err_str or "authentication" in err_str.lower():
            user_msg = "API key invalid. Please check your environment configuration."

        return jsonify({
            "error": user_msg,
            "message": err_str,
            "trace": traceback.format_exc() if app.debug else None,
        }), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)