import json,re,sys
hid=sys.argv[1]; pats=[re.compile(p,re.I) for p in sys.argv[2:]]
for h in map(json.loads,open('/home/alex/code/personal/memory-challenge/test/histories.jsonl')):
    if h['history_id']!=hid: continue
    for s in h['sessions']:
        for t in s['turns']:
            for sent in re.split(r'(?<=[.!?])\s+|\n+',t['content']):
                if all(p.search(sent) for p in pats):
                    print(s['date'][:10], s['session_id'], t['role'][:4], '|', sent[:230].replace('\n',' '))
