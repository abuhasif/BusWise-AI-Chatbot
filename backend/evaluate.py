"""Small, explicit end-to-end evaluation. Never uses the LLM as its own judge."""
import json,time
from pathlib import Path
from server import answer
cases=[
 ('How can I go from Serangoon to Bartley?',{},'route','158'),
 ('I am at Serangoon and want to reach Bartley. Which direct bus could I take?',{},'route','158'),
 ('Which buses serve stop 66009?',{},'stop','100'),
 ('Please tell me the services available at bus stop 66009.',{},'stop','100'),
 ('Last bus for service 100 at stop 66009 on Sunday?',{},'times','Last bus'),
 ('What about Saturday?',{'intent':'times','stop':'66009','service':'100','day':'sun'},'times','Saturday'),
 ('What about Aljunied?',{'intent':'route','origin':'Serangoon','destination':'Bartley'},'route','Aljunied'),
 ('Opposite direction',{'intent':'route','origin':'Serangoon','destination':'Bartley'},'route','Bartley'),
 ('When will the next bus arrive?',{},'unsupported','cannot confirm'),
 ('Is free boarding active now?',{},'unsupported','cannot confirm'),
 ('Buses at stop 99999',{},'stop','Which bus stop'),
 ('From Serangoon to Atlantis',{},'route','could not identify'),
]
results=[]
for question,context,intent,expected in cases:
 start=time.monotonic();result=answer(question,context);serialized=json.dumps(result)
 ok=result['context'].get('intent')==intent and expected in serialized
 results.append({'question':question,'passed':ok,'seconds':round(time.monotonic()-start,2),'result':result})
 print(('PASS' if ok else 'FAIL'),question,flush=True)
out=Path(__file__).resolve().parents[1]/'evaluation';out.mkdir(exist_ok=True)
(out/'live-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(f'{sum(x["passed"] for x in results)}/{len(results)} passed')
