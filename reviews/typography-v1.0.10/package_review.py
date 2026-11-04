#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,zipfile,shutil
ROOT=Path(__file__).resolve().parent
ARCHIVE=ROOT/'TYPOGRAPHY_REVIEW_PACKAGE.zip'
required=[ROOT/'TYPOGRAPHY_COMPARISON.pdf',ROOT/'TYPOGRAPHY_REVIEW.md',ROOT/'TYPOGRAPHY_IMPLEMENTATION.md',ROOT/'STABLE_INTEGRITY.json']
required += sorted((ROOT/'pdf').glob('*.pdf'))
assert len(list((ROOT/'pdf').glob('*.pdf')))==10
assert all(p.is_file() for p in required)
assert json.loads((ROOT/'STABLE_INTEGRITY.json').read_text())['status']=='passed'
assert json.loads((ROOT/'reports/DELIVERABLES_CHECK.json').read_text())['status']=='passed'
logs=ROOT/'logs';logs.mkdir(exist_ok=True)
for d in sorted((ROOT/'build').iterdir()):
    if not d.is_dir():continue
    for name in [d.name+'.log','driver.log']:
        p=d/name
        if p.is_file():shutil.copy2(p,logs/(d.name+('_driver.log' if name=='driver.log' else '.log')))
def include(p):
    rel=p.relative_to(ROOT);parts=rel.parts
    if p.is_symlink():return False
    if any(s in ['__pycache__','.venv','.git'] for s in parts):return False
    if parts[0]=='build':return False
    if parts[:2]==('fonts','downloads'):return False
    if parts[0]=='runtime' and (len(parts)<2 or parts[1] not in ['fonts','texmf']):return False
    if p.suffix in ['.aux','.out','.xdv','.fls','.fdb_latexmk'] or p.name.endswith('.synctex.gz'):return False
    if rel.as_posix() in ['TYPOGRAPHY_REVIEW_PACKAGE.zip','PACKAGE_SHA256.txt','PACKAGE_CONTENTS.json','SHA256SUMS.txt','PACKAGING_CHECK.json']:return False
    return p.is_file()
files=sorted(p for p in ROOT.rglob('*') if include(p))
entries=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
manifest={'purpose':'Independent typography review only; no stable changes approved or applied','core_pdf_count':11,'variant_pdf_count':10,'comparison_pages':25,'files':entries,'excluded':'Research font-download caches; compilation intermediates; binary TeX formats; runtime caches; original Git repository.'}
(ROOT/'PACKAGE_CONTENTS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
files.append(ROOT/'PACKAGE_CONTENTS.json');files.sort()
(ROOT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files))
files.append(ROOT/'SHA256SUMS.txt')
with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,(Path('typography-review')/p.relative_to(ROOT)).as_posix())
with zipfile.ZipFile(ARCHIVE) as z:
    assert z.testzip() is None
    for p in files:
        name=(Path('typography-review')/p.relative_to(ROOT)).as_posix()
        assert hashlib.sha256(z.read(name)).digest()==hashlib.sha256(p.read_bytes()).digest(),name
h=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
(ROOT/'PACKAGE_SHA256.txt').write_text(h+'  '+ARCHIVE.name+'\n')
check={'status':'passed','zip':ARCHIVE.name,'bytes':ARCHIVE.stat().st_size,'sha256':h,'members':len(files),'crc':'passed','all_archived_bytes_match_workspace':True,'stable_integrity':'passed','requested_core_pdfs':11}
(ROOT/'PACKAGING_CHECK.json').write_text(json.dumps(check,indent=2)+'\n')
for p in ROOT.rglob('*'):
    if p.is_dir():p.chmod(0o755)
    elif p.is_file():p.chmod(0o644)
print(json.dumps(check))
