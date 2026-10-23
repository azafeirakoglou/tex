#!/usr/bin/env python3
"""Export validated PDFs, a rendered preview and a source ZIP for review."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'dist')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sources = {
        'PRINT': ROOT/'build/print/Physics_A_Print_Technical.pdf',
        'SCREEN': ROOT/'build/screen/Physics_A_Screen.pdf',
    }
    report_path = ROOT/'build/validation/report.json'
    if not report_path.exists():
        parser.error('Run make preflight before exporting')
    report = json.loads(report_path.read_text())
    palette = json.loads((ROOT/'config/color-map.json').read_text())
    actual = {key.lower(): sha(path) for key, path in sources.items()}
    actual['palette'] = hashlib.sha256(json.dumps(palette, sort_keys=True).encode()).hexdigest()
    if report.get('status') != 'passed' or report.get('input_sha256') != actual:
        parser.error('Preflight is failed or stale; run make preflight on the current PDFs and palette')
    files = []
    for edition, source in sources.items():
        dest = out/f'Book_v0.33_{edition}.pdf'
        shutil.copyfile(source, dest)
        files.append(dest)
    # One actual representative book page per edition, without modifying the PDFs.
    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    font = ImageFont.truetype(font_path, 30) if Path(font_path).exists() else ImageFont.load_default()
    pages = []
    for edition, source in sources.items():
        with fitz.open(source) as doc:
            pix = doc[min(5, len(doc)-1)].get_pixmap(matrix=fitz.Matrix(1.65,1.65), alpha=False)
            page = Image.frombytes('RGB', [pix.width,pix.height], pix.samples)
            single = out/f'Book_v0.33_{edition}_preview.png'
            page.save(single)
            files.append(single)
            pages.append((edition,page))
    width = sum(page.width for _,page in pages)+60
    height = max(page.height for _,page in pages)+90
    comparison = Image.new('RGB',(width,height),'#eeeeee')
    draw = ImageDraw.Draw(comparison)
    left = 20
    for label,page in pages:
        draw.text((left,15),label+' — PROOF',font=font,fill='#222222')
        comparison.paste(page,(left,65))
        left += page.width+20
    preview = out/'Book_v0.33_comparison.png'
    comparison.save(preview)
    files.append(preview)
    validation = out/'validation.json'
    shutil.copyfile(report_path,validation)
    files.append(validation)
    guide = out/'START_HERE.txt'
    guide.write_text(
        'Universal Book Template v0.33\n\n'
        'PRINT: black + provisional red spot; SCREEN: black + blue. Both are proofs.\n'
        'If the chat PDF viewer fails, download/extract this ZIP and open the PDFs locally.\n'
        'The PNG comparison is a rendered preview, not a print master.\n'
        'For source/build instructions see source/README.md and source/SETUP.md.\n'
        'Printer ink, three tint percentages, bleed and PDF/X remain pending.\n',encoding='utf-8')
    files.append(guide)
    archive = out/'Universal_Book_Template_v0.33.zip'
    excluded = {'.git','.local','.venv','build','dist','releases','__pycache__'}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(ROOT.rglob('*')):
            rel = path.relative_to(ROOT)
            if path.is_file() and not any(part in excluded for part in rel.parts):
                if path.suffix not in {'.aux','.log','.out','.toc','.xdv','.pyc'}:
                    bundle.write(path,Path('source')/rel)
        for path in files:
            bundle.write(path,path.name)
        for path in sorted((ROOT/'.local/licenses').glob('*')):
            if path.is_file():
                bundle.write(path,Path('font-licenses')/path.name)
        summary = ROOT/'build/build-summary.json'
        if summary.exists():
            bundle.write(summary,'build-summary.json')
        for path in sorted((ROOT/'build/validation').glob('*.json')):
            bundle.write(path,Path('reports')/path.name)
    files.append(archive)
    manifest = out/'SHA256SUMS.txt'
    manifest.write_text(''.join(sha(p)+'  '+p.name+'\n' for p in files),encoding='utf-8')
    files.append(manifest)
    # Readable by a separate file-serving process, not only this shell user.
    out.chmod(0o755)
    for path in files:
        path.chmod(0o644)
        print(path.name, path.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
