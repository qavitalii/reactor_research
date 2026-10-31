"""Optional live-model regression: run with .venv/bin/python tests/eval_followups.py."""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

spec = importlib.util.spec_from_file_location('recall_server', Path(__file__).parents[1] / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

cases = [
    ('generic amount', 'яка сума була', 'The approved budget is 7300 PLN.', [], ['7300'], False),
    ('paraphrased amount', 'Скільки грошей погодили?', 'The approved budget is 8600 UAH.', [], ['8600'], False),
    ('ambiguous amount', 'яка сума була', 'The budget is 9100 EUR. The deposit is 600 EUR.', [], ['9100', '600'], False),
    ('followup deposit', 'яка сума була', 'The budget is 9100 EUR. The deposit is 600 EUR.', ['Що відомо про завдаток?'], ['600'], False),
    ('missing amount', 'яка сума була', 'The workshop took place on 12 November 2026.', [], [], True),
    ('generic date', 'коли це було', 'The workshop took place on 12 November 2026.', [], ['12', '2026'], False),
]
for name, question, text, history, values, abstain in cases:
    result = server.answer({'question': question, 'previous_questions': history,
        'sources': [{'source_id': 's1', 'title': 'Note', 'turns': [{'content': text}]}]})
    print(json.dumps({'case': name, 'result': result}, ensure_ascii=False), flush=True)
    assert result['abstain'] == abstain, name
    assert all(value in result['answer'] for value in values), name
    assert abstain or result['citations'], name
    assert all(c['quote'] in text for c in result['citations']), name
    if name == 'paraphrased amount':
        assert not any(phrase in result['answer'].lower() for phrase in ['не зазначено', 'немає', 'не вказує']), name
    if name == 'generic date':
        assert 'November' in result['answer'] or 'листопад' in result['answer'], name
    if name == 'followup deposit':
        assert '9100' not in result['answer'], name
print('All 6 live-model cases passed.', flush=True)
