import xml.etree.ElementTree as ET
import os

def convert_to_path(el):
    tag = el.tag.split('}')[-1]
    if tag == 'path':
        return el.attrib.get('d', '')
    elif tag == 'circle':
        cx = float(el.attrib.get('cx', 0))
        cy = float(el.attrib.get('cy', 0))
        r = float(el.attrib.get('r', 0))
        return f"M {cx},{cy} m -{r},0 a {r},{r} 0 1,0 {r*2},0 a {r},{r} 0 1,0 -{r*2},0"
    elif tag == 'line':
        x1 = float(el.attrib.get('x1', 0))
        y1 = float(el.attrib.get('y1', 0))
        x2 = float(el.attrib.get('x2', 0))
        y2 = float(el.attrib.get('y2', 0))
        return f"M {x1},{y1} L {x2},{y2}"
    elif tag == 'rect':
        x = float(el.attrib.get('x', 0))
        y = float(el.attrib.get('y', 0))
        w = float(el.attrib.get('width', 0))
        h = float(el.attrib.get('height', 0))
        rx = float(el.attrib.get('rx', 0))
        ry = float(el.attrib.get('ry', rx))
        if rx > 0:
            return f"M {x+rx},{y} h {w-2*rx} a {rx},{ry} 0 0,1 {rx},{ry} v {h-2*ry} a {rx},{ry} 0 0,1 -{rx},{ry} h -{w-2*rx} a {rx},{ry} 0 0,1 -{rx},-{ry} v -{h-2*ry} a {rx},{ry} 0 0,1 {rx},-{ry} z"
        else:
            return f"M {x},{y} h {w} v {h} h -{w} z"
    elif tag == 'polyline' or tag == 'polygon':
        points = el.attrib.get('points', '').strip().split()
        if not points: return ''
        d = f"M {points[0]}"
        for p in points[1:]:
            d += f" L {p}"
        if tag == 'polygon':
            d += " z"
        return d
    return ''

def process_svg(svg_file, out_file):
    tree = ET.parse(svg_file)
    root = tree.getroot()
    paths = []
    
    for el in root.iter():
        d = convert_to_path(el)
        if d:
            paths.append(d)
    
    if not paths: return
    
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24.0"
    android:viewportHeight="24.0">
"""
    for d in paths:
        xml += f"""    <path
        android:pathData="{d}"
        android:strokeColor="#FFFFFF"
        android:strokeWidth="2"
        android:strokeLineCap="round"
        android:strokeLineJoin="round"/>
"""
    xml += "</vector>\n"
    
    with open(out_file, 'w') as f:
        f.write(xml)

icons = ['house', 'heart', 'activity', 'battery-full', 'battery-medium', 'battery-low', 'bluetooth', 'message-square', 'bell', 'refresh-cw', 'cloud-sun', 'book-user', 'music', 'terminal', 'chevron-right', 'droplet', 'stethoscope', 'footprints', 'moon']

for icon in icons:
    svg_path = f"/root/dev/lucide-icons/lucide-main/icons/{icon}.svg"
    out_path = f"/root/dev/WatchApp/app/src/main/res/drawable/ic_{icon.replace('-','_')}.xml"
    if os.path.exists(svg_path):
        process_svg(svg_path, out_path)
        print(f"Generated {out_path}")
    else:
        print(f"NOT FOUND: {svg_path}")

