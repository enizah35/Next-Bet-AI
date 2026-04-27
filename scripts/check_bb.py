import urllib.request, json

r = urllib.request.urlopen('http://localhost:8000/predictions/upcoming?league=Ligue+1')
data = json.loads(r.read().decode())
for m in data:
    bb = m.get('betBuilder', {})
    sels = []
    for s in bb.get('selections', []):
        sels.append(f"{s['key']}({s['confidence']}%,@{s['odds']})")
    print(f"{m['homeTeam']:20s} vs {m['awayTeam']:20s} => {sels}")
