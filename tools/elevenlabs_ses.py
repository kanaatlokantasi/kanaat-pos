# ElevenLabs ile Türkçe yemek adı sesleri üretir (GitHub Actions'ta çalışır).
# Örnek modu: menu/ses-ornek.txt varsa sadece oradaki adları iki modelle seslendirir -> menu/ses-ornek/
# Tam mod:   menu/ses11.onay varsa menu/ses.txt'teki tüm adları seslendirir -> menu/ses11/<kod>.mp3 (var olan atlanır)
import os, json, urllib.request, sys
KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE = "UeybxBRjI6mrBwoIZOKU"
if not KEY:
    print("HATA: ELEVENLABS_API_KEY secret bulunamadi"); sys.exit(1)
def tts(text, model, out):
    body = {"text": text, "model_id": model,
            "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.0, "use_speaker_boost": True}}
    if model != "eleven_multilingual_v2": body["language_code"] = "tr"
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_64",
        data=json.dumps(body).encode(), headers={"xi-api-key": KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: data = r.read()
    except urllib.error.HTTPError as e:
        print("HATA", e.code, e.read()[:300].decode(errors="ignore")); return False
    open(out, "wb").write(data); return True
lines = [l.rstrip("\n").split("\t") for l in open("menu/ses.txt", encoding="utf-8") if l.strip()]
n = 0
if os.path.exists("menu/ses-ornek.txt"):
    os.makedirs("menu/ses-ornek", exist_ok=True)
    for i, name in enumerate([l.strip() for l in open("menu/ses-ornek.txt", encoding="utf-8") if l.strip()], 1):
        for m, tag in [("eleven_multilingual_v2", "A"), ("eleven_turbo_v2_5", "B")]:
            out = f"menu/ses-ornek/{i}-{tag}.mp3"
            if not os.path.exists(out) and tts(name, m, out): n += 1
if os.path.exists("menu/ses-dene.txt"):
    os.makedirs("menu/ses-dene", exist_ok=True)
    for i, l in enumerate([l.rstrip("\n") for l in open("menu/ses-dene.txt", encoding="utf-8") if l.strip()], 1):
        m, text = l.split("\t", 1)
        out = f"menu/ses-dene/{i}.mp3"
        if not os.path.exists(out) and tts(text, m, out): n += 1
# Özel mod: menu/ses-ozel.txt satırları: ad<TAB>ses_id<TAB>model<TAB>stability<TAB>speed<TAB>metin -> menu/ses-ozel/<ad>.mp3
if os.path.exists("menu/ses-ozel.txt"):
    os.makedirs("menu/ses-ozel", exist_ok=True)
    for l in [l.rstrip("\n") for l in open("menu/ses-ozel.txt", encoding="utf-8") if l.strip()]:
        nm, vid, mdl, stb, spd, text = l.split("\t", 5)
        out = f"menu/ses-ozel/{nm}.mp3"
        if os.path.exists(out): continue
        body = {"text": text, "model_id": mdl, "voice_settings": {"stability": float(stb), "similarity_boost": 0.75, "speed": float(spd)}}
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_64",
            data=json.dumps(body).encode(), headers={"xi-api-key": KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r: open(out, "wb").write(r.read()); n += 1
        except urllib.error.HTTPError as e:
            print("HATA", e.code, e.read()[:300].decode(errors="ignore"))
if os.path.exists("menu/ses11.onay"):
    model = open("menu/ses11.onay", encoding="utf-8").read().strip() or "eleven_multilingual_v2"
    os.makedirs("menu/ses11", exist_ok=True)
    for row in lines:
        h, text = row[0], row[1]
        m = row[2] if len(row) > 2 and row[2] else model
        out = f"menu/ses11/{h}.mp3"
        if os.path.exists(out) and os.path.getsize(out) > 0: continue
        if tts(text, m, out): n += 1
print("uretilen:", n)
