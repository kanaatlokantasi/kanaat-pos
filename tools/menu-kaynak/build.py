# Kanaat QR menü derleyici: items.txt + template.html -> kanaat-pos/menu/
# (15.11.2026'da yeniden yazıldı; çıktısı v103 ile birebir doğrulandı)
import json, zlib, hashlib, os, re, sys

VERSION = "121 · 27.11.2026"
REMOTE = "https://public.takeaseat.io/restaurants/7abc0ee3-bfdc-497b-91a6-ef20a58bacec/"
B = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.environ.get("ITEMS", os.path.join(B, "items.txt"))
TEMPLATE = os.environ.get("TEMPLATE", os.path.join(B, "template.html"))
OUT = os.environ.get("OUT", os.path.join(B, "..", "kanaat-pos", "menu"))
IMGDIR = os.path.join(B, "..", "kanaat-pos", "menu", "img")
CATS = ["soup", "kofte", "rice", "veg", "meat", "grill", "olive", "salad", "compote",
        "dessert", "drink", "togo", "yog", "jam"]
CAT_TR = {"soup": "Çorbalar", "kofte": "Köfteler", "rice": "Pilavlar", "veg": "Sebze yemekleri",
          "meat": "Et yemekleri", "grill": "Izgaralar", "olive": "Zeytinyağlılar", "salad": "Salatalar",
          "compote": "Kompostolar", "dessert": "Tatlılar", "drink": "İçecekler", "togo": "Kiloluk tatlılar",
          "yog": "Yoğurt", "jam": "Reçeller"}

def b36(n):
    s = ""
    while n:
        n, r = divmod(n, 36); s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
    return s or "0"

def code(cat, tr):
    return b36(zlib.crc32(f"{cat}|{tr}".encode()) % 36**4).rjust(4, "0")

FOLD = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
def slug(img):
    return img.translate(FOLD).lower().replace(" ", "-")

def trlower(s):
    return s.replace("I", "ı").replace("İ", "i").lower()

ONES = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
def num2tr(n):
    n = int(n)
    if n == 0: return "sıfır"
    out = []
    if n >= 1000:
        k = n // 1000; out.append("bin" if k == 1 else num2tr(k) + " bin"); n %= 1000
    if n >= 100:
        h = n // 100; out.append("yüz" if h == 1 else ONES[h] + " yüz"); n %= 100
    if n >= 10: out.append(TENS[n // 10]); n %= 10
    if n: out.append(ONES[n])
    return " ".join(out)

# Elle seçilmiş okunuşlar: ad -> (metin, model; boş = varsayılan)
SAY_OVR = {
    "Kazandibi (4'lü)": ("Dörtlü kazandibi.", ""),
    "Ayva Tatlısı (1 kg)": ("Bir kiloluk ayva tatlısı.", "eleven_multilingual_v2"),
    "Rulo Kaymak (250 gr)": ("İki yüz elli gram rulo kaymak.", ""),
    "Reçel - Kaymak": ("Reçel ve Kaymak", ""),
    "Vişneli Ekmek Kadayıfı (Kaymaklı)": ("Kaymaklı vişneli ekmek kadayıfı.", ""),
}

def spoken(name):
    if name in SAY_OVR: return SAY_OVR[name]
    m = re.match(r"^(.*?) \((.*)\)$", name)
    if not m: return (name, "")
    base, q = m.group(1), m.group(2)
    qs = [x.strip() for x in q.split(",")]
    if "1 kg" in qs:
        pre = [trlower(x) for x in qs if x != "1 kg"]
        return ("Bir kiloluk " + " ".join(pre + [trlower(base)]) + ".", "")
    q = re.sub(r"\d+", lambda d: num2tr(d.group(0)), q)
    return (base + ", " + q, "")

def say_hash(name, text, model):
    key = name if text == name and not model else text + "|" + model
    return hashlib.sha1(key.encode()).hexdigest()[:10]

THUMB = 240
def make_thumb(loc):
    """Liste için küçük kopya: img/k/<loc> (240 px). Kaynak yoksa False."""
    src = os.path.join(IMGDIR, loc); dst = os.path.join(IMGDIR, "k", loc)
    if not os.path.exists(src): return False
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src): return True
    from PIL import Image
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im = Image.open(src).convert("RGB"); w, h = im.size; s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((THUMB, THUMB), Image.LANCZOS)
    im.save(dst, "JPEG", quality=80, optimize=True, progressive=True)
    return True

def main():
    az = json.load(open(os.path.join(B, "azrules.json"), encoding="utf-8"))
    cats = {c: [] for c in CATS}
    for n, line in enumerate(open(ITEMS, encoding="utf-8").read().split("\n")):
        if not line.strip() or line.startswith("#"): continue
        f = line.split("|")
        cat, tr, price, img, kcal, meat, alg, diet, notes, trn = f[:10]
        diet_l = diet.split(",") if diet else []
        if "V" in diet_l and "v" not in diet_l:  # vegan ise vejetaryen de
            diet_l.insert(diet_l.index("V") + 1, "v")
        it = {"id": f"i{n}", "c": code(cat, tr), "tr": tr, "p": int(price), "img": img}
        if img: it["loc"] = slug(img)
        if img and make_thumb(it["loc"]): it["th"] = 1
        it.update({"kcal": int(kcal) if kcal else None, "meat": list(meat),
                   "alg": alg.split(",") if alg else [], "diet": diet_l,
                   "notes": notes.split(",") if notes else [], "trn": trn, "t": f[10:33]})
        assert len(it["t"]) == 23, (tr, len(it["t"]))
        for k, v in az.get(tr, {}).items(): it[k] = v
        cats[cat].append(it)
    menu = [{"id": c, "items": cats[c]} for c in CATS if cats[c]]
    items = [it for c in menu for it in c["items"]]

    sayh, rows = {}, {}
    for it in items:
        text, model = spoken(it["tr"])
        h = say_hash(it["tr"], text, model); sayh[it["tr"]] = h; rows[h] = (text, model)

    t = open(TEMPLATE, encoding="utf-8").read()
    html = (t.replace("__DATA__", json.dumps(menu, ensure_ascii=False, separators=(",", ":")))
             .replace("__SAYH__", json.dumps(sayh, ensure_ascii=False, separators=(",", ":")))
             .replace("__REMOTE__", REMOTE).replace("__VER__", VERSION))
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)

    with open(os.path.join(OUT, "ses.txt"), "w", encoding="utf-8") as fo:
        for h in sorted(rows):
            text, model = rows[h]
            fo.write(h + "\t" + text + ("\t" + model if model else "") + "\n")

    names = {it["c"]: it["tr"] for it in items}
    nophoto = [[CAT_TR[c["id"]], it["tr"]] for c in menu for it in c["items"]
               if not it["img"] or not os.path.exists(os.path.join(IMGDIR, it["loc"]))]
    st = open(os.path.join(B, "stats.html"), encoding="utf-8").read()
    st = (st.replace("__NAMES__", json.dumps(names, ensure_ascii=False, separators=(",", ":")))
            .replace("__NOPHOTO__", json.dumps(nophoto, ensure_ascii=False)).replace("__VER__", VERSION))
    os.makedirs(os.path.join(OUT, "istatistik"), exist_ok=True)
    open(os.path.join(OUT, "istatistik", "index.html"), "w", encoding="utf-8").write(st)

    sw = open(os.path.join(B, "sw.js"), encoding="utf-8").read().replace("__VER__", VERSION)
    open(os.path.join(OUT, "sw.js"), "w", encoding="utf-8").write(sw)

    nimg = len({it["loc"] for it in items if it["img"]})
    print(f"{len(menu)} cats {len(items)} items {nimg} images {len(html.encode())//1024} KB")

if __name__ == "__main__":
    main()
