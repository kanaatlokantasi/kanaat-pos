"""Kanaat Ödemeler: son günü yarın olan ödemeler için telefonlara bildirim gönderir.

GitHub Actions her sabah 10:00'da (TR) çalıştırır. Firebase hizmet hesabı anahtarı
FIREBASE_SA gizli değişkeninden okunur. Depo herkese açık olduğu için bu betik
loglara ödeme, tutar ya da kişi bilgisi YAZMAZ; yalnızca sayılar yazılır.
"""
import json
import os
import sys
import datetime
from zoneinfo import ZoneInfo

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

APP_URL = "https://kanaatlokantasi.github.io/kanaat-pos/odemeler/"
TUR = {"maas": "Banka maaşları", "et": "Et", "kdv": "KDV", "kredikarti": "Kredi kartları", "sgk": "SGK primi",
       "stopaj": "Muhtasar / stopaj", "gecici": "Geçici vergi", "kurumlar": "Kurumlar vergisi",
       "oda": "Ticaret odası aidatı", "resmi": "Diğer resmi gider", "kira": "Kira", "kaymak": "Kaymak",
       "benzin": "Benzin", "ekmek": "Ekmek", "yogurt": "Yoğurt", "su": "Taşkesti su", "turkcell": "Turkcell",
       "iski": "İSKİ", "dogalgaz": "Doğalgaz", "elektrik": "Elektrik"}
SKIP_DOCS = {"_seriler", "_kalemler"}


def val(v):
    if "stringValue" in v: return v["stringValue"]
    if "integerValue" in v: return int(v["integerValue"])
    if "doubleValue" in v: return float(v["doubleValue"])
    if "booleanValue" in v: return v["booleanValue"]
    if "nullValue" in v: return None
    if "timestampValue" in v: return v["timestampValue"]
    if "mapValue" in v: return {k: val(x) for k, x in v["mapValue"].get("fields", {}).items()}
    if "arrayValue" in v: return [val(x) for x in v["arrayValue"].get("values", [])]
    return None


def tl(n):
    if n is None:
        return "tutar girilmedi"
    if abs(n - round(n)) < 0.005:
        return f"{int(round(n)):,}".replace(",", ".") + " ₺"
    s = f"{n:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " ₺"


def main():
    raw = os.environ.get("FIREBASE_SA", "").strip()
    if not raw:
        print("FIREBASE_SA gizli değişkeni henüz eklenmemiş; bildirim gönderilmedi.")
        return 0
    sa = json.loads(raw)
    pid = sa["project_id"]
    cred = service_account.Credentials.from_service_account_info(
        sa, scopes=["https://www.googleapis.com/auth/datastore", "https://www.googleapis.com/auth/firebase.messaging"])
    cred.refresh(Request())
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + cred.token
    base = f"https://firestore.googleapis.com/v1/projects/{pid}/databases/(default)/documents"

    def docs(col):
        out, tok = [], None
        while True:
            r = s.get(f"{base}/{col}", params={"pageSize": 300, **({"pageToken": tok} if tok else {})}, timeout=30)
            r.raise_for_status()
            j = r.json()
            for d in j.get("documents", []):
                out.append((d["name"].rsplit("/", 1)[1], {k: val(x) for k, x in d.get("fields", {}).items()}))
            tok = j.get("nextPageToken")
            if not tok:
                return out

    test = os.environ.get("TEST") == "1"
    users = {uid for uid, _ in docs("users")}
    tokens = [(t, d) for t, d in docs("tokens")]

    if test:
        title, body, tag = "Test bildirimi", "Kanaat Ödemeler bildirimleri bu telefonda çalışıyor.", "test"
        url = APP_URL
    else:
        tomorrow = (datetime.datetime.now(ZoneInfo("Europe/Istanbul")).date() + datetime.timedelta(days=1)).isoformat()
        pays = dict(docs("payments"))
        custom = (pays.get("_kalemler") or {}).get("items") or {}
        due = [p for i, p in pays.items() if i not in SKIP_DOCS and not p.get("paid") and p.get("vade") == tomorrow]
        print(f"Yarın son günü olan bekleyen ödeme: {len(due)}")
        if not due:
            return 0
        lab = lambda t: TUR.get(t) or custom.get(t) or t
        if len(due) == 1:
            p = due[0]
            title = f"Yarın son gün: {lab(p.get('tur'))}"
            body = " · ".join(x for x in [p.get("acik"), tl(p.get("tutar"))] if x)
        else:
            title = f"Yarın {len(due)} ödemenin son günü"
            body = ", ".join(f"{lab(p.get('tur'))} {tl(p.get('tutar'))}" for p in due)
            if len(body) > 230:
                body = body[:227] + "…"
        tag = "odeme-" + tomorrow
        url = APP_URL + "?gun=" + tomorrow

    sent = removed = failed = 0
    for tok, d in tokens:
        if d.get("uid") not in users:  # erişimi kaldırılmış kişi
            s.delete(f"{base}/tokens/{tok}", timeout=30)
            removed += 1
            continue
        msg = {"message": {"token": tok,
                           "data": {"title": title, "body": body, "url": url, "tag": tag},
                           "webpush": {"headers": {"Urgency": "high", "TTL": "43200"}}}}
        r = s.post(f"https://fcm.googleapis.com/v1/projects/{pid}/messages:send", json=msg, timeout=30)
        if r.ok:
            sent += 1
            continue
        err = ""
        try:
            err = json.dumps(r.json().get("error", {}))
        except Exception:
            pass
        if r.status_code == 404 or "UNREGISTERED" in err or ("INVALID_ARGUMENT" in err and "token" in err.lower()):
            s.delete(f"{base}/tokens/{tok}", timeout=30)  # telefon artık bildirim almıyor
            removed += 1
        else:
            failed += 1
            print(f"Gönderilemedi: HTTP {r.status_code}")
    print(f"Gönderilen: {sent} · geçersiz olduğu için silinen: {removed} · hata: {failed} · kayıtlı telefon: {len(tokens)}")
    return 1 if failed and not sent else 0


if __name__ == "__main__":
    sys.exit(main())
