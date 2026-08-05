import re

def convert(lat_deg, lat_min, lat_hemi,
            lon_deg, lon_min, lon_hemi):

    lat = int(lat_deg) + float(lat_min) / 60
    lon = int(lon_deg) + float(lon_min) / 60

    if lat_hemi == "S":
        lat = -lat

    if lon_hemi == "W":
        lon = -lon

    return round(lat, 6), round(lon, 6)


coords = []

with open("input.txt", "r") as f:

    for line in f:

        m = re.search(
            r'(\d+)-([\d.]+)([NS])\s+(\d+)-([\d.]+)([EW])',
            line
        )

        if m:

            lat, lon = convert(
                m.group(1),
                m.group(2),
                m.group(3),
                m.group(4),
                m.group(5),
                m.group(6)
            )

            coords.append((lat, lon))

xml = []

xml.append('<?xml version="1.0" encoding="UTF-8"?>')
xml.append('<userchart name="TEST" version="1.3">')
xml.append('<areas>')
xml.append(
    '<area name="NAVAREA IV 539/2026" description="UNDERWATER OPERATIONS">'
)
xml.append('<position>')

for i, (lat, lon) in enumerate(coords, start=1):

    xml.append(
        f'<vertex id="{i}" latitude="{lat}" longitude="{lon}"/>'
    )

xml.append('</position>')
xml.append('<attribute linkedDocument=""/>')
xml.append('<type checkDanger="1" displayRadar="0" hasNotes="0" notesType="0"/>')
xml.append('<display S52colorcode="CHRED" lineWidth="3" density="25"/>')
xml.append('</area>')
xml.append('</areas>')
xml.append('</userchart>')

with open("output.xml", "w") as f:
    f.write("\n".join(xml))

print("Done")
