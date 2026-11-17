"""Builds public/epg.xml.gz: all EX-YU channels from several open EPG sources.

- Channels listed in channels.txt (the ones the playlist uses) are always kept with their ids.
- Every other channel from the sources is added once (duplicates across sources are merged
  by normalized name; the source with the most programmes wins).
- mk.xml (iptv-org grab of extra channels) is added as-is.
"""
import gzip, io, os, re, sys, unicodedata, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

SOURCES = [
    # epgshare01
    "https://epgshare01.online/epgshare01/epg_ripper_RS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_HR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BA1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_SPORTKLUB1.xml.gz",
    # open-epg.com public country files
    "https://www.open-epg.com/files/macedonia.xml",
    "https://www.open-epg.com/files/macedonia1.xml",
    "https://www.open-epg.com/files/serbia1.xml",
    "https://www.open-epg.com/files/serbia2.xml",
    "https://www.open-epg.com/files/serbia3.xml",
    "https://www.open-epg.com/files/serbia4.xml",
    "https://www.open-epg.com/files/serbia5.xml",
    "https://www.open-epg.com/files/croatia.xml",
    "https://www.open-epg.com/files/croatia1.xml",
    "https://www.open-epg.com/files/croatia2.xml",
    "https://www.open-epg.com/files/bosnia.xml",
    "https://www.open-epg.com/files/bosnia1.xml",
    "https://www.open-epg.com/files/montenegro.xml",
    "https://www.open-epg.com/files/slovenia.xml",
]
EXTRA_FILES = ["mk.xml"]  # local grabs (iptv-org)

wanted = {l.strip() for l in open("channels.txt", encoding="utf-8") if l.strip()}
cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).strftime("%Y%m%d%H%M%S")

def norm(name):
    s = unicodedata.normalize("NFD", name.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "dj")
    s = re.sub(r"\.(rs|hr|ba|mk|me|si|ex)$", "", s)
    s = re.sub(r"\((rs|sr|hr|bih|bh|si|mk|me|cg|int|w2|portals?)\)", " ", s)
    s = re.sub(r"\b(hd|fhd|uhd|4k|sd|tv|televizija|channel)\b", " ", s)
    s = s.replace("&", "and").replace("+", "plus")
    return re.sub(r"[^a-z0-9а-я]", "", s)

# id -> {"el": channel element, "progs": [...], "name": str}
chans = {}

def load(stream, label):
    local = {}
    for _, el in ET.iterparse(stream, events=("end",)):
        if el.tag == "channel":
            cid = el.get("id")
            if cid and cid not in local:
                local[cid] = {"el": el, "progs": [], "name": (el.findtext("display-name") or cid)}
        elif el.tag == "programme":
            cid = el.get("channel")
            stop = (el.get("stop") or el.get("start") or "")[:14]
            if cid and stop >= cutoff[:len(stop)]:
                local.setdefault(cid, {"el": None, "progs": [], "name": cid})["progs"].append(el)
    n = 0
    for cid, c in local.items():
        if not c["progs"]:
            continue
        if c["el"] is None:
            c["el"] = ET.Element("channel", {"id": cid}); ET.SubElement(c["el"], "display-name").text = cid
        old = chans.get(cid)
        if old is None or len(c["progs"]) > len(old["progs"]):
            chans[cid] = c
        n += 1
    print(f"{label}: {n} channels with programmes")

for url in SOURCES:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=240).read()
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        load(io.BytesIO(data), url)
    except Exception as e:
        print("FAILED", url, e, file=sys.stderr)

for f in EXTRA_FILES:
    if os.path.exists(f) and os.path.getsize(f) > 0:
        try:
            load(f, f)
        except Exception as e:
            print("FAILED", f, e, file=sys.stderr)

# choose: wanted ids always; otherwise one channel per normalized name
keep, taken = [], set()
for cid in sorted(wanted):
    if cid in chans:
        keep.append(cid); taken.add(norm(chans[cid]["name"])); taken.add(norm(cid))
best = {}
for cid, c in chans.items():
    if cid in wanted:
        continue
    k = norm(c["name"]) or norm(cid)
    if not k or k in taken:
        continue
    if k not in best or len(c["progs"]) > len(chans[best[k]]["progs"]):
        best[k] = cid
keep += sorted(best.values(), key=lambda x: chans[x]["name"].lower())

root = ET.Element("tv", {"generator-info-name": "exyu-epg"})
total = 0
for cid in keep:
    root.append(chans[cid]["el"])
for cid in keep:
    for p in chans[cid]["progs"]:
        root.append(p); total += 1

os.makedirs("public", exist_ok=True)
with gzip.open("public/epg.xml.gz", "wb", compresslevel=9) as f:
    ET.ElementTree(root).write(f, encoding="utf-8", xml_declaration=True)
with open("public/channels.txt", "w", encoding="utf-8") as f:
    for cid in keep:
        f.write(f"{cid}\t{chans[cid]['name']}\t{len(chans[cid]['progs'])}\n")
print("wanted kept:", sum(1 for c in keep if c in wanted), "/", len(wanted))
print("channels:", len(keep), "programmes:", total)
if total < 1000:
    sys.exit("Too few programmes - not publishing")
