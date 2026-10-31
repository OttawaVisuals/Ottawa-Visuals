"""Independent audit against the downloaded PBO PDFs and StatCan HTML table.

Run after downloading the original PBO reports to output/wealth-research/.
Requires PyMuPDF for PDF extraction; it is not required to build the page.
"""
import json
from pathlib import Path
import re
import urllib.request
from html.parser import HTMLParser
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
H = json.loads((ROOT / 'data/historical-transcription.json').read_text(encoding='utf-8'))
RAW = ROOT.parent / 'output/wealth-research'


def numeric_rows(page, labels, count):
    lines = [s.strip() for s in page.get_text().splitlines() if s.strip()]
    result = {}
    for label in labels:
        # Older PDFs omit the space in e.g. "Top 0.01%".
        indices = [i for i, line in enumerate(lines) if line.replace(' ', '') == label.replace(' ', '')]
        assert len(indices) == 1, (label, indices)
        vals = lines[indices[0]+1:indices[0]+1+count]
        result[label] = [None if v == 'N/A' else float(v.replace(',', '')) for v in vals]
    return result


def main():
    reports = {edition: pymupdf.open(RAW / f'pbo{edition}.pdf') for edition in ['2021', '2025']}
    d=H['pbo_history_2021']
    extracted=numeric_rows(reports['2021'][10], d['groups'], 8)
    for i, group in enumerate(d['groups']):
        assert extracted[group] == [v for pair in zip(d['cb'][i], d['forbes'][i]) for v in pair], group
    groups=H['percentile_groups']
    for s, page in zip(H['snapshots'], [reports['2021'][7], reports['2021'][8], reports['2025'][10], reports['2025'][12]]):
        # Bottom/middle rows have range strings; verify numeric columns separately.
        lines=[x.strip() for x in page.get_text().splitlines() if x.strip()]
        for i,g in enumerate(groups):
            index=next(j for j,line in enumerate(lines) if line.replace(' ','')==g.replace(' ',''))
            values=lines[index+1:index+5]
            assert [float(v.replace(',','')) for v in values[1:]] == [s['families_thousands'][i],s['wealth_billions'][i],s['shares'][i]], (s['id'],g,values)
            a=re.sub(r'\s+','',values[0].lower()).replace('–','-')
            b=re.sub(r'\s+','',s['threshold_millions'][i].lower()).replace('–','-')
            assert a==b,(s['id'],g,a,b)
    for year,page in [('2019',reports['2021'][7]),('2023',reports['2025'][11])]:
        d=H['thresholds'][year]
        extracted=numeric_rows(page,H['thresholds']['labels'],3)
        for i,g in enumerate(H['thresholds']['labels']):
            assert extracted[g]==[d['families_thousands'][i],d['wealth_billions'][i],d['shares'][i]],(year,g)
    # Newer report's figure text tables have exact numbers, so no digitization.
    d=H['pbo_history_2025']
    for i,page in enumerate([reports['2025'][13],reports['2025'][14]]):
        compact=' '.join(page.get_text().split())
        for key,label in [('survey','SFS Only (%)'),('forbes','SFS + Forbes (%)'),('enriched','(%)')]:
            expected=' '.join('N/A' if v is None else f'{v:.1f}' for v in d[key][i])
            assert expected in compact,(i,key,expected)
    class Table(HTMLParser):
        def __init__(self): super().__init__();self.rows=[];self.row=None;self.cell=None
        def handle_starttag(self,tag,attrs):
            if tag=='tr':self.row=[]
            if tag in ('td','th'):self.cell=''
        def handle_data(self,text):
            if self.cell is not None:self.cell+=text
        def handle_endtag(self,tag):
            if tag in ('td','th') and self.cell is not None:
                if self.row is not None:self.row.append(self.cell.strip())
                self.cell=None
            if tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None
    parser=Table();parser.feed(urllib.request.urlopen(H['sources']['statcan2006']['table_url']).read().decode('utf-8'))
    rows=[r for r in parser.rows if len(r)>=9 and r[0] in ['Bottom 10%','Second','Third','Fourth','Fifth','Sixth','Seventh','Eighth','Ninth','Top 10%']][:10]
    assert len(rows)==10,len(rows)
    study=H['historical_studies'][1]
    for i,row in enumerate(rows):
        nums=[float(v.replace(',','')) for v in row[1:] if re.fullmatch(r'-?[\d,]+(?:\.\d+)?',v)]
        assert nums[:3]==[a[i] for a in study['decile_medians_2005_dollars']],row
        assert nums[3:6]==[a[i] for a in study['decile_shares']],row
    print('PBO history, four percentile snapshots, two threshold tables, and all 2006-study deciles match primary source numeric tables.')


if __name__=='__main__': main()
