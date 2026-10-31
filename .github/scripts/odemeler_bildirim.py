"""Kanaat Ödemeler: son günü yarın olan ödemeler için telefonlara bildirim gönderir.

GitHub Actions her sabah 10:00'da (TR) çalıştırır. Firebase hizmet hesabı anahtarı
FIREBASE_SA gizli değişkeninden okunur. Depo herkese açık olduğu için bu betik
loglara ödeme, tutar ya da kişi bilgisi YAZMAZ; yalnızca sayılar yazılır.
"""
import json
import os
import re
import sys
import datetime
from zoneinfo import ZoneInfo

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

APP_URL = "https://kanaatlokantasi.github.io/kanaat-pos/odemeler/"
REMIND_DAYS = 3  # tutarı girilmemiş ödeme için son günden kaç gün öncesinden itibaren hatırlatılsın
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


def parse_ts(x):
    """Firestore zaman damgası ("2026-10-28T11:20:00.123456Z") → UTC datetime"""
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?Z$", x or "") if isinstance(x, str) else None
    if not m:
        return None
    return datetime.datetime.fromisoformat(m.group(1) + "." + (m.group(2) or "")[:6].ljust(6, "0") + "+00:00")


def ddmm(d):
    try:
        y, m, g = d.split("-")
        return f"{g}.{m}"
    except Exception:
        return ""


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
    mode = os.environ.get("MODE", "")
    users_d = dict(docs("users"))
    users = set(users_d)
    tokens = [(t, d) for t, d in docs("tokens")]

    msgs = []
    make = None  # telefona özel bildirim (olay modunda: kişinin kendi yaptığı değişiklik ona gönderilmez)
    if mode == "olay" and not test:
        # ---- ödendi işaretlenen ve yeni eklenen ödemeler (her 5 dakikada bir) ----
        now = datetime.datetime.now(datetime.timezone.utc)
        st_url = f"{base}/meta/bildirim"
        r = s.get(st_url, timeout=30)
        last = None
        if r.ok:
            last = parse_ts(val(r.json().get("fields", {}).get("last", {"nullValue": None})))
        elif r.status_code != 404:
            r.raise_for_status()

        def save_last():
            s.patch(st_url, params={"updateMask.fieldPaths": "last"}, timeout=30,
                    json={"fields": {"last": {"timestampValue": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")}}}).raise_for_status()

        if last is None:  # ilk çalıştırma: geçmiş değişiklikler için bildirim gönderme
            save_last()
            print("İlk çalıştırma: başlangıç zamanı kaydedildi.")
            return 0
        last = max(last, now - datetime.timedelta(hours=6))
        pays = dict(docs("payments"))
        custom = (pays.get("_kalemler") or {}).get("items") or {}
        lab = lambda t: TUR.get(t) or custom.get(t) or t
        events = []
        for i, p in pays.items():
            if i in SKIP_DOCS:
                continue
            a = parse_ts(p.get("addedAt"))
            if a and last < a <= now and p.get("addedBy"):  # düzenli ödemeler ("Otomatik") dahil
                events.append(("ekle", p, p.get("addedBy"), p.get("addedByUid"), a))
            pd = parse_ts(p.get("paidAt"))
            if p.get("paid") and pd and last < pd <= now and p.get("paidBy"):
                events.append(("ode", p, p.get("paidBy"), p.get("paidByUid"), pd))
        msgs = []
        for i, m in docs("msgs"):
            a = parse_ts(m.get("at"))
            if a and last < a <= now and m.get("text"):
                m["_id"] = i
                msgs.append(m)
                events.append(("msj", m, m.get("fromName") or "Yönetici", m.get("from"), a))
        events.sort(key=lambda e: e[4])
        save_last()  # önce kaydet: bir hata olursa aynı bildirim ikinci kez gitmesin
        print(f"Yeni olay: {len(events)}")
        if not events:
            return 0
        stamp = now.strftime("%Y%m%d%H%M")

        def make(d):
            evs = [e for e in events if not ((e[3] and e[3] == d.get("uid")) or (not e[3] and e[2] == d.get("name")))
                   and (e[0] != "msj" or e[1].get("to") in ("*", d.get("uid")))]
            if not evs:
                return None
            if len(evs) == 1:
                kind, p, by, _, _ = evs[0]
                if kind == "msj":
                    t = f"Mesaj: {by}"
                    b = p.get("text", "")
                elif kind == "ode":
                    t = f"Ödendi: {lab(p.get('tur'))}"
                    b = " · ".join(x for x in [p.get("acik"), tl(p.get("tutar")), f"{by} işaretledi"] if x)
                else:
                    auto = by == "Otomatik"
                    t = f"{'Yeni düzenli ödeme' if auto else 'Yeni ödeme'}: {lab(p.get('tur'))}"
                    b = " · ".join(x for x in [p.get("acik"), tl(p.get("tutar")),
                                               f"son ödeme {ddmm(p.get('vade'))}" if p.get("vade") else "",
                                               "" if auto else f"{by} ekledi"] if x)
                u = APP_URL + ("?gun=" + p["vade"] if kind != "msj" and p.get("vade") else "")
            else:
                t = f"{len(evs)} yeni bildirim" if any(e[0] == "msj" for e in evs) else f"{len(evs)} ödeme güncellemesi"
                b = "; ".join(f"✉ {by}: {p.get('text', '')[:60]}" if k == "msj"
                              else f"✓ {lab(p.get('tur'))} ödendi ({by})" if k == "ode"
                              else f"+ {lab(p.get('tur'))} {ddmm(p.get('vade'))} (düzenli)" if by == "Otomatik"
                              else f"+ {lab(p.get('tur'))} eklendi ({by})"
                              for k, p, by, _, _ in evs)
                u = APP_URL
            if len(b) > 230:
                b = b[:227] + "…"
            return t, b, u, "olay-" + stamp
    elif test:
        title, body, tag = "Test bildirimi", "Kanaat Ödemeler bildirimleri bu telefonda çalışıyor.", "test"
        url = APP_URL
        # testte de dokununca açılan ekranı denemek için en yakın bekleyen ödemenin gününü bağla
        today = datetime.datetime.now(ZoneInfo("Europe/Istanbul")).date().isoformat()
        days = sorted({p.get("vade") for i, p in docs("payments")
                       if i not in SKIP_DOCS and not p.get("paid") and (p.get("vade") or "") >= today})
        if days:
            y, m, g = days[0].split("-")
            url = APP_URL + "?gun=" + days[0]
            body = f"Bildirimler çalışıyor. Dokunun: {g}.{m}.{y} tarihli ödemeler açılacak."
    else:
        # ---- her sabah 10:00 ----
        today_d = datetime.datetime.now(ZoneInfo("Europe/Istanbul")).date()
        tomorrow = (today_d + datetime.timedelta(days=1)).isoformat()
        last_rem = (today_d + datetime.timedelta(days=REMIND_DAYS)).isoformat()
        pays = dict(docs("payments"))
        custom = (pays.get("_kalemler") or {}).get("items") or {}
        lab = lambda t: TUR.get(t) or custom.get(t) or t
        open_p = [p for i, p in pays.items() if i not in SKIP_DOCS and not p.get("paid")]
        due = [p for p in open_p if p.get("vade") == tomorrow]
        # tutarı girilmemiş, son günü 1-3 gün sonra olan ödemeler (tutar hatırlatması açık kişilere)
        missing = sorted([p for p in open_p if p.get("tutar") is None and tomorrow <= (p.get("vade") or "") <= last_rem],
                         key=lambda p: p.get("vade"))
        remind_uids = {uid for uid, u in users_d.items() if u.get("tutarHatirlat")}
        print(f"Yarın son günü olan bekleyen ödeme: {len(due)} · tutarı eksik ödeme: {len(missing)} · hatırlatılacak kişi: {len(remind_uids)}")
        general = None
        if due:
            if len(due) == 1:
                p = due[0]
                t = f"Yarın son gün: {lab(p.get('tur'))}"
                b = " · ".join(x for x in [p.get("acik"), tl(p.get("tutar"))] if x)
            else:
                t = f"Yarın {len(due)} ödemenin son günü"
                b = ", ".join(f"{lab(p.get('tur'))} {tl(p.get('tutar'))}" for p in due)
            general = (t, b[:227] + "…" if len(b) > 230 else b, APP_URL + "?gun=" + tomorrow, "odeme-" + tomorrow)
        reminder = None
        if missing and remind_uids:
            if len(missing) == 1:
                p = missing[0]
                t = f"Tutar girilmedi: {lab(p.get('tur'))}"
                b = " · ".join(x for x in [p.get("acik"), f"son ödeme {ddmm(p.get('vade'))}", "Tutarı girmeyi unutmayın."] if x)
            else:
                t = f"{len(missing)} ödemenin tutarı girilmedi"
                b = "; ".join(f"{lab(p.get('tur'))} · son ödeme {ddmm(p.get('vade'))}" for p in missing) + ". Tutarları girmeyi unutmayın."
            reminder = (t, b[:227] + "…" if len(b) > 230 else b, APP_URL + "?gun=" + missing[0]["vade"], "tutar-" + today_d.isoformat())
        if not general and not reminder:
            return 0

        def make(d):
            out = [general] if general else []
            if reminder and d.get("uid") in remind_uids:
                out.append(reminder)
            return out

    sent = removed = failed = 0
    pushed_msgs = set()
    for tok, d in tokens:
        if d.get("uid") not in users:  # erişimi kaldırılmış kişi
            s.delete(f"{base}/tokens/{tok}", timeout=30)
            removed += 1
            continue
        out = make(d) if make else [(title, body, url, tag)]
        if not out:
            continue
        if isinstance(out, tuple):
            out = [out]
        for title, body, url, tag in out:
          msg = {"message": {"token": tok,
                             "data": {"title": title, "body": body, "url": url, "tag": tag},
                             "webpush": {"headers": {"Urgency": "high", "TTL": "43200"}}}}
          r = s.post(f"https://fcm.googleapis.com/v1/projects/{pid}/messages:send", json=msg, timeout=30)
          if r.ok:
              sent += 1
              if mode == "olay":
                  for e in events:
                      if e[0] == "msj" and e[1].get("to") in ("*", d.get("uid")) and e[3] != d.get("uid"):
                          pushed_msgs.add(e[1]["_id"])
              continue
          err = ""
          try:
              err = json.dumps(r.json().get("error", {}))
          except Exception:
              pass
          if r.status_code == 404 or "UNREGISTERED" in err or ("INVALID_ARGUMENT" in err and "token" in err.lower()):
              s.delete(f"{base}/tokens/{tok}", timeout=30)  # telefon artık bildirim almıyor
              removed += 1
              break
          else:
              failed += 1
              print(f"Gönderilemedi: HTTP {r.status_code}")
    if mode == "olay" and not test and sent:
        # mesajlar için "telefona bildirim gitti" bilgisini kaydet
        stamp_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        for m in msgs:
            if m["_id"] in pushed_msgs:
                s.patch(f"{base}/msgs/{m['_id']}", params={"updateMask.fieldPaths": "pushedAt"}, timeout=30,
                        json={"fields": {"pushedAt": {"timestampValue": stamp_ts}}})
    print(f"Gönderilen: {sent} · geçersiz olduğu için silinen: {removed} · hata: {failed} · kayıtlı telefon: {len(tokens)}")
    return 1 if failed and not sent else 0


if __name__ == "__main__":
    sys.exit(main())
