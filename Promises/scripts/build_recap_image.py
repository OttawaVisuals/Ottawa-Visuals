"""Render a chart-only recap from the reviewed local promise snapshots."""
import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports'
OUT.mkdir(exist_ok=True)
tax = json.loads((ROOT / 'data/property-tax.json').read_text(encoding='utf-8'))
# Original user-supplied CMHC portal export; retain bytes and source metadata.
cmhc = list(csv.reader((ROOT / 'data/cmhc-ottawa-completions-2026-09.csv').read_text(encoding='cp1252').splitlines()))
assert cmhc[0][0].strip() == 'Ottawa (CV) — Historical Completions by Intended Market'
assert cmhc[1][0] == 'January 2001 to September 2026 Dwelling Types - All'
assert cmhc[2][1:6] == ['Homeowner', 'Rental', 'Condo', 'Co-Op', 'All']
annual, coverage, monthly = defaultdict(int), defaultdict(int), {}
for record in cmhc[3:]:
    if not record or not re.fullmatch(r'[A-Za-z]{3} \d{4}', record[0]):
        continue
    date = datetime.strptime(record[0], '%b %Y')
    values = [int(value.replace(',', '')) for value in record[1:6]]
    assert sum(values[:4]) == values[4], record
    assert (date.year, date.month) not in monthly, record
    monthly[date.year, date.month] = values[4]
    annual[date.year] += values[4]
    coverage[date.year] += 1
assert set(monthly) == {(year, month) for year in range(2001, 2027) for month in range(1, (9 if year == 2026 else 12)+1)}
assert annual[2023] == 7890 and annual[2024] == 8794 and annual[2025] == 7797
assert sum(monthly[2026, month] for month in range(1,9)) == 5559
assert monthly[2026,9] == 274 and annual[2026] == 5833
bus = json.loads((ROOT / 'data/bus-reliability.json').read_text(encoding='utf-8'))
INK, MUTED, GRID, BLUE, TEAL, ORANGE = '#172b3a', '#526473', '#dce3e7', '#2474a6', '#148477', '#ad5c25'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                     'text.color': INK, 'axes.labelcolor': MUTED,
                     'xtick.color': MUTED, 'ytick.color': MUTED,
                     'svg.fonttype': 'none', 'hatch.linewidth': 1.2})
fig = plt.figure(figsize=(15, 11.5), facecolor='white')
gs = fig.add_gridspec(2, 6, left=.065, right=.975, bottom=.075, top=.90,
                      hspace=.68, wspace=.80, height_ratios=[1.12, 1])

def style(ax, title, subtitle, ymax, ticks):
    ax.set_axisbelow(True)
    ax.grid(axis='y', color=GRID, linewidth=.8)
    for side in ['top', 'right', 'left']:
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    ax.tick_params(length=0, pad=9)
    ax.set_ylim(0, ymax)
    ax.set_yticks(ticks)
    ax.text(0, 1.20, title, transform=ax.transAxes, fontsize=18, weight='bold', va='bottom')
    ax.text(0, 1.07, subtitle, transform=ax.transAxes, fontsize=11, color=MUTED, va='bottom', linespacing=1.5)

ax = fig.add_subplot(gs[0, :3])
rows = [r for r in tax['years'] if r['year'] >= 2023]
style(ax, 'Municipal property-tax increases', 'Ottawa · adopted annual budget increases (%)', 4.7, [0, 1, 2, 3, 4])
ax.axhspan(2, 2.5, color=ORANGE, alpha=.10, zorder=0)
ax.axhline(2.5, color=ORANGE, linestyle=(0, (4, 3)), linewidth=1.5)
ax.text(.02, 4.4, '2022 pledge: 2–2.5%', transform=ax.get_yaxis_transform(), color=ORANGE, fontsize=11)
bars = ax.bar(range(4), [r['increase_pct'] for r in rows], width=.53, color=BLUE, zorder=3)
ax.bar_label(bars, labels=[f"{r['increase_pct']:g}%" for r in rows], padding=8, fontsize=16, weight='bold')
ax.set_xticks(range(4), ['2023\nFirm promise', '2024\nFirm promise', '2025\nTarget', '2026\nTarget'])
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:g}%'))

ax = fig.add_subplot(gs[0, 3:])
rows = [{'year': year, 'completions': annual[year], 'months': coverage[year]} for year in range(2023, 2027)]
style(ax, 'Homes completed in Ottawa', '2022 pledge: 100,000 homes over 10 years\nCMHC completions · Ottawa city · all dwelling types', 12000, [0, 2500, 5000, 7500, 10000])
ax.hlines(10000, -.45, 2.45, color=ORANGE, linestyle=(0, (4, 3)), linewidth=1.5)
ax.text(-.40, 10400, '10,000/year · illustrative pace¹', color=ORANGE, fontsize=11)
bars = ax.bar(range(4), [r['completions'] for r in rows], width=.53, color=TEAL)
bars[-1].set_facecolor('#d5ebe6')
bars[-1].set_edgecolor(TEAL)
bars[-1].set_hatch('///')
ax.bar_label(bars, labels=[f"{r['completions']:,}" for r in rows], padding=8, fontsize=16, weight='bold')
ax.set_xticks(range(4), ['2023', '2024', '2025', '2026\nJan–Sep only'])
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:,.0f}'))
ax.text(0, -.26, '¹ 100,000 ÷ 10; no annual milestone was promised.', transform=ax.transAxes, fontsize=10, color=MUTED)

metrics = [
    ('trips_delivered', 'Bus trips delivered', 'Scheduled trips that operated', '99.5% target · Q4 2027'),
    ('punctuality_less_frequent_routes', 'Bus punctuality', 'Less-frequent routes', '85% official target'),
    ('regularity_frequent_routes', 'Bus regularity', 'Frequent routes · spacing measure', '85% official target²'),
]
for i, (metric, title, definition, target_label) in enumerate(metrics):
    ax = fig.add_subplot(gs[1, 2*i:2*i+2])
    style(ax, title, f'OC Transpo · annual results (%)\n{definition}', 112, [0, 25, 50, 75, 100])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:g}%'))
    target = bus['targets'][metric]['value']
    ax.axhline(target, color=ORANGE, linestyle=(0, (4, 3)), linewidth=1.5)
    ax.text(.02, target+3, target_label, transform=ax.get_yaxis_transform(), color=ORANGE, fontsize=10)
    records = {int(r['period']): r['value'] for r in bus['records'] if r['metric']==metric and r['period_type']=='year'}
    for j, year in enumerate([2023, 2024, 2025]):
        if year in records:
            val = records[year]
            ax.bar(j, val, width=.53, color=BLUE)
            ax.text(j, val-9, f'{val:g}%', ha='center', va='center', color='white', fontsize=14, weight='bold')
        else:
            ax.text(j, 6, 'No annual\nresult', ha='center', color=MUTED, fontsize=10)
    ax.set_xlim(-.6, 2.6)
    ax.set_xticks([0,1,2], ['2023','2024','2025'])
    if i == 2:
        ax.text(0, -.21, '² Target date not established.\nOfficial KPI targets ≠ 2022 campaign promises.', transform=ax.transAxes, fontsize=9, color=MUTED, linespacing=1.5)

fig.savefig(OUT / 'ottawa-election-recap.png', dpi=160, facecolor='white')
fig.savefig(OUT / 'ottawa-election-recap.svg', facecolor='white')
print(OUT / 'ottawa-election-recap.png')
