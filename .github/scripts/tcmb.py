# TCMB günlük kur bülteninden EUR/USD/GBP döviz alış kurunu fx.json'a yazar.
import json, urllib.request, xml.etree.ElementTree as ET, datetime, sys
req = urllib.request.Request('https://www.tcmb.gov.tr/kurlar/today.xml', headers={'User-Agent': 'Mozilla/5.0 (kanaat-pos kur)'})
root = ET.fromstring(urllib.request.urlopen(req, timeout=30).read())
out = {'source': 'TCMB', 'kind': 'ForexBuying', 'date': root.get('Tarih'), 'bulletin': root.get('Bulten_No')}
for c in root.findall('Currency'):
    k = c.get('Kod')
    if k in ('EUR', 'USD', 'GBP'):
        unit = float(c.findtext('Unit') or 1)
        out[k] = round(float(c.findtext('ForexBuying')) / unit, 4)
if not all(out.get(k) for k in ('EUR', 'USD', 'GBP')):
    sys.exit('kur eksik: ' + json.dumps(out))
try:
    old = json.load(open('fx.json'))
except Exception:
    old = {}
if {k: old.get(k) for k in out} == out:
    print('değişiklik yok', out); sys.exit(0)
out['fetchedAt'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
json.dump(out, open('fx.json', 'w'), ensure_ascii=False, indent=1)
print('güncellendi', out)
