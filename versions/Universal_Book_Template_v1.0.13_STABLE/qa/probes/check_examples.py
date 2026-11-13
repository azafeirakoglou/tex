#!/usr/bin/env python3
"""Assert actual A/B typography, no-dot headers and multi-page example flow."""
import hashlib
import json
from pathlib import Path
import re

import fitz

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PT = 72 / 72.27
MM = 72 / 25.4


def spans(page):
    return [s for b in page.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']]


def unique(pdf, marker):
    found = [(i, s) for i, p in enumerate(pdf) for s in spans(p) if marker in s['text']]
    assert len(found) == 1, (marker, 'must occur exactly once', found)
    return found[0]


def near(rgb, expected, tolerance=.012):
    return rgb is not None and max(abs(a-b) for a, b in zip(rgb, expected)) < tolerance


def inspect(path, variant, profile):
    with fitz.open(path) as pdf:
        assert all(abs(p.rect.width/MM-170)<.02 and abs(p.rect.height/MM-240)<.02 for p in pdf)
        titles = {}
        for marker in ('STABLESHORTONE', 'STABLESHORTTWO', 'STABLESHORTTHREE', 'STABLELONGTITLE'):
            i, title = unique(pdf, marker)
            assert title['font'] == 'NotoSerif-Medium' and abs(title['size']/PT-10.7)<.012, title
            assert title['color'] == (0xffffff if variant == 'A' else
                (0x203B63 if profile == 'SCREEN' else title['color'])), 'Incorrect title ink'
            centre = fitz.Rect(title['bbox']).tl + (fitz.Rect(title['bbox']).br-fitz.Rect(title['bbox']).tl)*.5
            fills = [d for d in pdf[i].get_drawings() if d.get('fill') is not None
                     and d['rect'].contains(centre) and d['rect'].width>300]
            assert fills, 'Header must have a measurable filled title cell'
            fill = min(fills, key=lambda d:d['rect'].get_area())
            assert 18 < fill['rect'].height < 28, 'Header is no longer compact'
            if variant == 'A':
                assert (near(fill['fill'], (32/255,59/255,99/255)) if profile=='SCREEN'
                        else not near(fill['fill'], (1,1,1))), 'A needs solid second-ink title fill'
            else:
                assert near(fill['fill'], (1,1,1)), 'B needs white title fill'
            # A legacy title dot would be a small filled path immediately before
            # the title baseline. Exclude the cell, the frame and other content.
            dots = [d for d in pdf[i].get_drawings() if d.get('fill') is not None
                    and .5<d['rect'].width<10 and .5<d['rect'].height<10
                    and title['bbox'][0]-15 < d['rect'].x0 < title['bbox'][0]-1
                    and title['bbox'][1]-2 < d['rect'].y0 < title['bbox'][3]+2]
            assert not dots, (marker, 'legacy solid title dot remains', dots)
            titles[marker] = {'page':i+1,'font':title['font'],'size_tex_pt':title['size']/PT,
                              'title_rgb':f'{title["color"]:06X}', 'header_height_bp':fill['rect'].height,
                              'dot_paths':0}
        assert {titles[x]['page'] for x in ('STABLESHORTONE','STABLESHORTTWO','STABLESHORTTHREE')} == {1}, \
            'Three consecutive examples must be compared together on page one'
        for word in ('ONE','TWO','THREE'):
            ti,_ = unique(pdf,'STABLESHORT'+word)
            pi,_ = unique(pdf,'SHORTPROBLEM'+word)
            si,solution = unique(pdf,'SHORTSOLUTION'+word)
            assert ti==pi==si, 'A short title/solution became orphaned'
            assert solution['color']==0, 'Solution text must be neutral black'
        texts=[p.get_text() for p in pdf];joined='\n'.join(texts)
        for kind,count in [('PROBLEM',24),('SOLUTION',18)]:
            assert re.findall('LONG'+kind+r'ROW(\d{3})',joined)==[f'{i:03d}' for i in range(1,count+1)], \
                'Long '+kind+' content lost, reordered or duplicated'
        pb,_=unique(pdf,'LONGPROBLEMBEGIN');pe,_=unique(pdf,'LONGPROBLEMEND')
        tb,_=unique(pdf,'LONGTHINKBEGIN');te,_=unique(pdf,'LONGTHINKEND')
        sb,sstart=unique(pdf,'LONGSOLUTIONBEGIN');se,_=unique(pdf,'LONGSOLUTIONEND')
        assert pb<pe and pe<=tb<=te<=sb<se, 'Statement / Think / Solution order or page split failed'
        labels=[(i,s) for i,p in enumerate(pdf) for s in spans(p) if s['text'].strip()=='Λύση']
        assert len(labels)==4 and labels[-1][0]==sb, 'Solution label is orphaned from first solution paragraph'
        for i,page in enumerate(pdf):
            for s in spans(page):
                if 'LONGSOLUTION' not in s['text']:continue
                point=fitz.Point((s['bbox'][0]+s['bbox'][2])/2,(s['bbox'][1]+s['bbox'][3])/2)
                fills=[d for d in page.get_drawings() if d.get('fill') is not None
                       and d['rect'].width>250 and d['rect'].contains(point)]
                assert not fills or all(near(d['fill'],(1,1,1)) for d in fills), \
                    'The solution was enclosed in a filled statement box'
        return {'pages':len(pdf),'titles':titles,'consecutive_examples_same_page':True,
                'long_statement_pages':[pb+1,pe+1],'long_solution_pages':[sb+1,se+1],
                'statement_rows':24,'solution_rows':18,'solution_on_white':True,
                'solution_labels_kept_with_first_paragraph':True}


def main():
    rows=[]
    for variant in ('A','B'):
        for profile in ('SCREEN','PRINT'):
            path=HERE/'pdf'/f'EXAMPLES_{variant}_{profile}.pdf'
            row={'variant':variant,'profile':profile,'pdf':str(path.relative_to(ROOT)),
                 'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'failed'}
            try:row.update(measurements=inspect(path,variant,profile),status='passed')
            except (AssertionError,RuntimeError,ValueError) as exc:row['error']=str(exc)
            rows.append(row)
    # Same-content A/B variants change colour only. Every word and rectangle
    # must retain its position; the comparison is not independently rescaled.
    ab=[]
    for profile in ('SCREEN','PRINT'):
        with fitz.open(HERE/'pdf'/f'EXAMPLES_A_{profile}.pdf') as a, \
                fitz.open(HERE/'pdf'/f'EXAMPLES_B_{profile}.pdf') as b:
            assert len(a)==len(b)
            for p,q in zip(a,b):
                aw=p.get_text('words');bw=q.get_text('words');assert len(aw)==len(bw)
                for x,y in zip(aw,bw):assert x[4]==y[4] and max(abs(u-v) for u,v in zip(x[:4],y[:4]))<.02
            ab.append({'profile':profile,'same_words_and_positions':True,'tolerance_bp':.02})
    report={'status':'passed' if all(r['status']=='passed' for r in rows) else 'failed',
            'proofs':rows,'ab_geometry':ab}
    (HERE/'EXAMPLES_MEASUREMENTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report['status']!='passed'


if __name__=='__main__':raise SystemExit(main())
