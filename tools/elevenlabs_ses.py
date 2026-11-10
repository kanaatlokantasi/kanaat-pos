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
SP = {t: (h, t) for h, t in lines}
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
if os.path.exists("menu/ses11.onay"):
    model = open("menu/ses11.onay", encoding="utf-8").read().strip() or "eleven_multilingual_v2"
    os.makedirs("menu/ses11", exist_ok=True)
    for h, text in lines:
        out = f"menu/ses11/{h}.mp3"
        if os.path.exists(out) and os.path.getsize(out) > 0: continue
        if tts(text, model, out): n += 1
print("uretilen:", n)
