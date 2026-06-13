import os
import json
import glob
import re
from copy import deepcopy
from datetime import datetime

# Variables that are actually present in BrainEngine._read_market_context / sandbox eval.
# ob and ote are intentionally excluded: the current BrainEngine sandbox context
# sets them to False, so candidate rules requiring them can never match.
SUPPORTED_VARS = [
    'price', 'atr', 'body_ratio', 'choppy', 'momentum', 'break_bull', 'break_bear',
    'sentuh_high', 'sentuh_low', 'fvgs', 'm15_bias', 'h1_bias', 'recent_events'
]

UNSUPPORTED_KEYWORDS = [
    r'\brsi\b', r'\bmacd\b', r'\bvolume\b', r'\bstochastic\b', r'\b1h\b', r'\b4h\b',
    r'\bdaily\b', r'moving average', r'bollinger', r'\bema\b', r'\bsma\b',
    r'order block', r'optimal trade entry'
]

REQUIRED_FIELDS = ['name', 'direction', 'conditions', 'invalid_if', 'tp_logic', 'sl_logic', 'based_on']
_ALLOWED_WORDS = set(SUPPORTED_VARS) | {'true', 'false', 'True', 'False', 'and', 'or', 'not', 'contains', 'in'}
_IDENTIFIER_RE = re.compile(r'\b[A-Za-z_][A-Za-z0-9_]*\b')
_STRING_RE = re.compile(r'''("[^"\\]*(?:\\.[^"\\]*)*"|'[^'\\]*(?:\\.[^'\\]*)*')''')

def _identifiers(condition):
    without_strings = _STRING_RE.sub('', condition or '')
    return set(_IDENTIFIER_RE.findall(without_strings))

def unsupported_condition_reason(condition):
    cond_lower = (condition or '').lower()
    for kw in UNSUPPORTED_KEYWORDS:
        if re.search(kw, cond_lower):
            return 'menggunakan indikator/timeframe/konsep yang tidak tersedia di sandbox BrainEngine'

    identifiers = _identifiers(condition)
    unsupported_names = sorted(name for name in identifiers if name not in _ALLOWED_WORDS)
    if unsupported_names:
        return 'variabel tidak tersedia di sandbox BrainEngine: ' + ', '.join(unsupported_names)

    return None

def test_candidate(method):
    for field in REQUIRED_FIELDS:
        if field not in method:
            return {
                'name': method.get('name', 'UNKNOWN'),
                'status': 'INVALID_FORMAT',
                'reason': f'Missing required field: {field}',
                'valid_conditions': [],
                'unsupported_conditions': [],
                'recommendation': 'Buang candidate atau perbaiki format JSON'
            }

    if str(method.get('direction', '')).upper() not in ('BUY', 'SELL'):
        return {
            'name': method.get('name', 'UNKNOWN'),
            'status': 'INVALID_FORMAT',
            'reason': 'direction harus BUY atau SELL',
            'valid_conditions': [],
            'unsupported_conditions': [],
            'recommendation': 'Perbaiki direction candidate'
        }

    unsupported_conds = []
    valid_conds = []

    all_conds = list(method.get('conditions', [])) + list(method.get('invalid_if', []))
    for cond in all_conds:
        reason = unsupported_condition_reason(cond)
        if reason:
            unsupported_conds.append({'condition': cond, 'reason': reason})
        else:
            valid_conds.append(cond)

    if unsupported_conds:
        return {
            'name': method['name'],
            'status': 'UNSUPPORTED_CONDITION',
            'reason': 'Candidate memakai kondisi yang tidak tersedia atau tidak bisa dievaluasi sandbox engine',
            'valid_conditions': valid_conds,
            'unsupported_conditions': unsupported_conds,
            'recommendation': 'Revisi candidate: hapus kondisi unsupported atau buat varian relaxed sandbox'
        }

    return {
        'name': method['name'],
        'status': 'TESTABLE',
        'reason': 'Format valid dan semua kondisi memakai variabel sandbox BrainEngine',
        'valid_conditions': valid_conds,
        'unsupported_conditions': [],
        'recommendation': 'Lanjut test manual atau sederhanakan dulu untuk sandbox'
    }

def simplify_method(method):
    direction = str(method.get('direction', '')).upper()
    if direction not in ('BUY', 'SELL'):
        return None

    relaxed = deepcopy(method)
    base_name = method.get('name', 'AI_METHOD_UNKNOWN')
    if not base_name.endswith('_SANDBOX_RELAXED'):
        relaxed['name'] = f'{base_name}_SANDBOX_RELAXED'

    if direction == 'BUY':
        relaxed['conditions'] = [
            'sentuh_low == true',
            "momentum == 'bullish'",
            'body_ratio >= 0.20'
        ]
        relaxed['invalid_if'] = ['break_bear == true']
    else:
        relaxed['conditions'] = [
            'sentuh_high == true',
            "momentum == 'bearish'",
            'body_ratio >= 0.20'
        ]
        relaxed['invalid_if'] = ['break_bull == true']

    relaxed['based_on'] = method.get('based_on', 'candidate') + '_sandbox_relaxed'
    relaxed['why_this_method'] = (
        'Sandbox relaxed variant: memakai variabel yang benar-benar tersedia di BrainEngine '
        'dan mengurangi konfirmasi wajib agar candidate bisa menghasilkan trade awal.'
    )
    relaxed['avoid_conditions'] = [
        'Tidak memakai ob/ote karena belum tersedia di sandbox BrainEngine',
        'Tidak memakai choppy sebagai invalid_if awal agar tidak memblokir semua entry'
    ]
    relaxed['confidence_reason'] = 'Validasi awal sandbox: sweep level + momentum candle + body_ratio minimum'
    return relaxed

def main():
    candidate_files = glob.glob('brain_versions/ai_method_candidates_*.json')
    if not candidate_files:
        print('Tidak ada file candidate method ditemukan.')
        return

    report = {
        'generated_at': datetime.now().isoformat(),
        'files_tested': len(candidate_files),
        'total_candidates': 0,
        'testable_count': 0,
        'unsupported_count': 0,
        'invalid_count': 0,
        'results': []
    }

    for cfile in candidate_files:
        try:
            with open(cfile, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f'Error reading {cfile}: {e}')
            continue

        methods = data.get('methods', [])
        report['total_candidates'] += len(methods)

        file_result = {'file': cfile, 'candidates': []}

        for m in methods:
            res = test_candidate(m)
            file_result['candidates'].append(res)
            if res['status'] == 'TESTABLE':
                report['testable_count'] += 1
            elif res['status'] == 'UNSUPPORTED_CONDITION':
                report['unsupported_count'] += 1
            else:
                report['invalid_count'] += 1

        report['results'].append(file_result)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f'brain_versions/candidate_test_report_{timestamp}.json'

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f'Candidate testing complete! Laporan disimpan di {report_file}')
    print(f'Total Candidates: {report["total_candidates"]}')
    print(f'TESTABLE: {report["testable_count"]}')
    print(f'UNSUPPORTED: {report["unsupported_count"]}')
    print(f'INVALID: {report["invalid_count"]}')

if __name__ == '__main__':
    main()
