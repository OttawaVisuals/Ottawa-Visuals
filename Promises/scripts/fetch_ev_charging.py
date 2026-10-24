"""Deliberately refresh the EV locator snapshot. Normal page builds do not fetch."""
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT.parent / 'Ottawa_Elections/Ottawa_Election_Wards_Only.json'
CACHE = Path(os.environ.get('TEMP', '/tmp')) / 'ottawa-ev-afdc.json'
URL = 'https://developer.nlr.gov/api/alt-fuel-stations/v1.json?api_key=DEMO_KEY&fuel_type=ELEC&country=CA&state=ON&limit=all'
REVIEWED = '2026-10-24'


def decode_wards(topology):
    scale, translate = topology['transform']['scale'], topology['transform']['translate']
    arcs = []
    for arc in topology['arcs']:
        x = y = 0
        points = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append([x * scale[0] + translate[0], y * scale[1] + translate[1]])
        arcs.append(points)
    result = []
    for geometry in next(iter(topology['objects'].values()))['geometries']:
        assert geometry['type'] == 'Polygon'
        rings = []
        for ids in geometry['arcs']:
            ring = []
            for n in ids:
                ring.extend((arcs[n] if n >= 0 else list(reversed(arcs[~n])))[:-1])
            rings.append(ring)
        result.append({'ward': geometry['properties']['Ward'], 'rings': rings})
    return result


def inside(x, y, ring):
    hit = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def build_snapshot():
    if '--refresh' in sys.argv or not CACHE.exists():
        with urllib.request.urlopen(URL, timeout=45) as response:
            CACHE.write_bytes(response.read())
    raw = CACHE.read_bytes()
    payload = json.loads(raw)
    assert payload['total_results'] == len(payload['fuel_stations']), 'Truncated API response'
    wards = decode_wards(json.loads(BOUNDARY.read_text(encoding='utf-8')))
    stations = []
    excluded = {'not_available': 0, 'not_public': 0, 'unverified': 0, 'future_date': 0}
    in_boundary = 0
    fields = ['id', 'station_name', 'street_address', 'city', 'zip', 'latitude', 'longitude', 'open_date', 'date_last_confirmed', 'updated_at', 'access_code', 'access_days_time', 'restricted_access', 'owner_type_code', 'ev_network', 'ev_level1_evse_num', 'ev_level2_evse_num', 'ev_dc_fast_num', 'status_code']
    for record in payload['fuel_stations']:
        ward = next((w['ward'] for w in wards if inside(record['longitude'], record['latitude'], w['rings'][0]) and not any(inside(record['longitude'], record['latitude'], r) for r in w['rings'][1:])), None)
        if ward is None:
            continue
        in_boundary += 1
        reason = 'not_available' if record['status_code'] != 'E' else 'not_public' if record['access_code'] != 'public' else 'unverified' if record.get('unverified') else 'future_date' if record.get('open_date') and record['open_date'] > REVIEWED else None
        if reason:
            excluded[reason] += 1
            continue
        s = {k: record.get(k) for k in fields}
        s['ward'] = ward
        s['hydro_named'] = any(n in s['station_name'].lower() for n in ['hydro ottawa', 'envari'])
        counts = [s[k] for k in ['ev_level1_evse_num', 'ev_level2_evse_num', 'ev_dc_fast_num']]
        s['ports'] = sum(v or 0 for v in counts) if any(v is not None for v in counts) else None
        stations.append(s)
    return {'reviewed': REVIEWED, 'source_url': URL, 'source_sha256': hashlib.sha256(raw).hexdigest(), 'ontario_records': len(payload['fuel_stations']), 'in_boundary_records': in_boundary, 'excluded_sequentially': excluded, 'boundary_path': str(BOUNDARY.relative_to(ROOT.parent)).replace('\\', '/'), 'boundary_sha256': hashlib.sha256(BOUNDARY.read_bytes()).hexdigest(), 'stations': sorted(stations, key=lambda s: s['id']), 'wards': wards,
            'method': 'Current Ontario locator snapshot; point-in-polygon in existing simplified 2022 Ottawa ward boundaries, then status E, access public, not flagged unverified, no future listed date. Public may have customer/access restrictions. Station records are not deduplicated physical sites; ports are current capacity, not opening-year capacity. Hydro-named is a text match, not verified ownership, installation or campaign attribution. Open dates can be first listing dates. No historical network reconstruction or promise completion percentage.'}


if __name__ == '__main__':
    data = build_snapshot()
    (ROOT / 'data/ev-charging.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Retained {len(data['stations'])} available public locator records; review counts and labels before publishing.")
