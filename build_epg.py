"""Builds epg.xml.gz: epgshare01 (RS/HR/BA/Sport Klub) filtered to the playlist's channels + Macedonian guide (mk.xml)."""
import gzip, io, os, sys, urllib.request
import xml.etree.ElementTree as ET

SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_RS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_HR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BA1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_SPORTKLUB1.xml.gz",
]
wanted = {l.strip() for l in open("channels.txt", encoding="utf-8") if l.strip()}
root = ET.Element("tv", {"generator-info-name": "exyu-epg"})
channels, programmes, seen = [], [], set()

def take(stream, only_wanted=True):
    n = 0
    for _, el in ET.iterparse(stream, events=("end",)):
        if el.tag == "channel":
            cid = el.get("id")
            if (not only_wanted or cid in wanted) and cid not in seen:
                seen.add(cid); channels.append(el)
        elif el.tag == "programme":
            if not only_wanted or el.get("channel") in wanted:
                programmes.append(el); n += 1
    return n

for url in SOURCES:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=180).read()
        print(url, "programmes:", take(io.BytesIO(gzip.decompress(data))))
    except Exception as e:
        print("FAILED", url, e, file=sys.stderr)

if os.path.exists("mk.xml") and os.path.getsize("mk.xml") > 0:
    try:
        print("mk.xml programmes:", take("mk.xml", only_wanted=False))
    except Exception as e:
        print("FAILED mk.xml", e, file=sys.stderr)

root.extend(channels); root.extend(programmes)
os.makedirs("public", exist_ok=True)
with gzip.open("public/epg.xml.gz", "wb") as f:
    ET.ElementTree(root).write(f, encoding="utf-8", xml_declaration=True)
print("channels:", len(channels), "programmes:", len(programmes))
if len(programmes) < 1000:
    sys.exit("Too few programmes - not publishing")
