"""Live retrieval regression: requires the installed local Ollama models."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import server

notes = {
    'budget': 'The approved budget is 7300 PLN.',
    'refund': 'Participants may cancel their booking up to two days before arrival and receive their money back.',
    'owner': 'Maya is responsible for coordinating supplier deliveries.',
    'delay': 'The launch was postponed because the security review has not been completed.',
    'badge': 'The access badge is inside the drawer at reception.',
    'date': 'The workshop took place on 12 November 2026.',
}
noise = [
    'The office plants need watering every Friday. Keep the soil moist and use the green watering can.',
    'Lunch is served at noon in the cafeteria. The menu includes vegetable soup and fresh bread.',
    'The design guide uses a green accent and large headings. Buttons have rounded corners and clear labels.',
    'The archive contains landscape photographs. Each picture shows mountains, lakes or forest paths.',
    'The technical manual describes how to change printer cartridges. Open the cover and remove the empty cartridge.',
]
sources = [{'source_id': f'noise-{i}', 'title': f'Archive note {i}',
            'turns': [{'content': noise[i % len(noise)] * 8}]} for i in range(35)]
sources += [{'source_id': key, 'title': 'Note', 'turns': [{'content': text}]} for key, text in notes.items()]
assert sum(len(s['turns'][0]['content']) for s in sources) > 18000
cases = [
    ('яка сума була', 'budget'),
    ('Скільки грошей погодили?', 'budget'),
    ('How much funding got the green light?', 'budget'),
    ('Ile pieniędzy zatwierdzono?', 'budget'),
    ('Чи можна повернути кошти, якщо плани змінилися?', 'refund'),
    ('Хто займається постачанням?', 'owner'),
    ('Why did we move the release date?', 'delay'),
    ('Де залишили перепустку?', 'badge'),
    ('Коли відбувся захід?', 'date'),
]
started = time.monotonic()
for question, expected in cases:
    body = {'question': question, 'sources': sources}
    selected, partial = server.excerpts(body)
    ids = [c['source_id'] for c in selected[:3]]
    print(json.dumps({'question': question, 'top3': ids, 'expected': expected}, ensure_ascii=False), flush=True)
    assert partial and expected in ids, (question, ids)
    results = server.search(body)['results']
    assert expected in [r['source_id'] for r in results], (question, results)
    assert all(r['quote'] in next(s for s in sources if s['source_id'] == r['source_id'])['turns'][0]['content'] for r in results)
assert server.search({'question': 'What is the population of Neptune?', 'sources': sources})['results'] == []
for question, expected in [cases[0], cases[4], cases[5]]:
    result = server.answer({'question': question, 'sources': sources})
    print(json.dumps({'question': question, 'answer': result}, ensure_ascii=False), flush=True)
    assert not result['abstain'] and expected in [c['source_id'] for c in result['citations']], question
    assert all(c['quote'] in next(s for s in sources if s['source_id'] == c['source_id'])['turns'][0]['content'] for c in result['citations'])
print(f'Passed 9 paraphrase/cross-language retrieval cases, 1 unrelated query and 3 grounded answers in {time.monotonic() - started:.1f}s.', flush=True)
