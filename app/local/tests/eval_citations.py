"""Live regression for PDF layout, contract summaries and exact original citations."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import server

# Synthetic document: no personal information from the user's PDF is retained here.
document = ('UMOWA\tO\tDZIEŁO\n§1\nZamawiający\nzamawia,\ta\nWykonawca\n'
            'przyjmuje\tdo\twykonania\tdzieło:\tNapisanie\tautorskiego\tkodu\tprogramistycznego\tw\tjęzyku\n'
            'Python,\tobejmującego\topracowanie\tkonsolowego\tsystemu\tzarządzania\tmagazynem\tz\twykorzystaniem\tbazy\tdanych\tSQLite,\n'
            'obsługą\tproduktów,\tstanów\tmagazynowych\ti\tcen.\n§2\nTermin\twykonania\tdzieła\tustala\tsię\tod\n'
            '04.09.2026\ndo\n28.10.2026\n.\n§3\nZa\twykonanie\tdzieła\nZamawiający\n'
            'zobowiązuje\tsię\tzapłacić\nWykonawcy\nwynagrodzenie\tw\twysokości\n8300\nzłotych\tbrutto.\n'
            'Wynagrodzenie\tbędzie\tpłatne\tnajpóźniej\t14\tdni\tpo\tprzedłożeniu\trachunku.')
source = {'source_id': 'synthetic-contract', 'title': 'Service agreement.pdf · Page 1', 'turns': [{'content': document}]}
for question, values in [('про що умова?', ['Python', 'SQLite']),
                         ('Яка сума винагороди за роботу?', ['8300']),
                         ('До коли потрібно завершити роботу?', ['28.10.2026'])]:
    result = server.answer({'question': question, 'sources': [source]})
    print(json.dumps({'question': question, 'answer': result['answer'], 'type': result['type'],
                      'quotes': len(result['citations'])}, ensure_ascii=False), flush=True)
    assert result['type'] == 'model' and not result['abstain'], question
    assert all(value in result['answer'] for value in values), question
    assert result['citations'] and all(c['source_id'] == source['source_id'] and c['quote'] in document for c in result['citations'])
print('All 3 PDF layout and citation cases passed.', flush=True)
