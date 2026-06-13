import argparse
import glob
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.candidate_method_tester import simplify_method, test_candidate

def _latest_candidate_file():
    files = glob.glob('brain_versions/ai_method_candidates_*.json')
    return max(files, key=os.path.getctime) if files else None

def _load_json(path, default):
    if not path or not os.path.exists(path):
        return default
    with open(path, 'r') as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description='Build relaxed sandbox brain from latest TESTABLE AI candidates.')
    parser.add_argument('--candidate', help='Candidate JSON path. Default: latest brain_versions/ai_method_candidates_*.json')
    parser.add_argument('--sandbox', default='brain_versions/sandbox_brain_current.json', help='Sandbox brain output path')
    parser.add_argument('--replace', action='store_true', help='Replace sandbox methods instead of appending relaxed variants')
    parser.add_argument('--max-methods', type=int, default=4, help='Max relaxed methods to add')
    args = parser.parse_args()

    candidate_path = args.candidate or _latest_candidate_file()
    if not candidate_path:
        print('Tidak ada candidate JSON ditemukan.')
        sys.exit(1)

    candidate_data = _load_json(candidate_path, {'methods': []})
    sandbox_data = {'methods': []} if args.replace else _load_json(args.sandbox, {'methods': []})

    methods_by_name = {}
    for method in sandbox_data.get('methods', []):
        name = method.get('name')
        if name:
            methods_by_name[name] = method

    added = []
    skipped = []
    for method in candidate_data.get('methods', []):
        result = test_candidate(method)
        if result['status'] != 'TESTABLE':
            skipped.append({'name': method.get('name', 'UNKNOWN'), 'status': result['status'], 'reason': result['reason']})
            continue

        relaxed = simplify_method(method)
        if not relaxed:
            skipped.append({'name': method.get('name', 'UNKNOWN'), 'status': 'INVALID_FORMAT', 'reason': 'Tidak bisa simplify direction'})
            continue

        name = relaxed['name']
        if name in methods_by_name:
            continue

        methods_by_name[name] = relaxed
        added.append(name)
        if len(added) >= args.max_methods:
            break

    output = {
        'methods': list(methods_by_name.values()),
        'sandbox_meta': {
            'updated_at': datetime.now().isoformat(),
            'source_candidate_file': candidate_path,
            'mode': 'append_relaxed_candidates',
            'added_relaxed_methods': added,
            'skipped_candidates': skipped
        }
    }

    os.makedirs(os.path.dirname(args.sandbox), exist_ok=True)
    with open(args.sandbox, 'w') as f:
        json.dump(output, f, indent=4)

    print(f'Sandbox brain updated: {args.sandbox}')
    print(f'Source candidate: {candidate_path}')
    print(f'Added relaxed methods: {len(added)}')
    for name in added:
        print(f'- {name}')
    if skipped:
        print(f'Skipped candidates: {len(skipped)}')

if __name__ == '__main__':
    main()
