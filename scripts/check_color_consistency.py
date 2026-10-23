#!/usr/bin/env python3
"""Έλεγχος πηγών/παλέτας. Ο τελικός έλεγχος μελανιών γίνεται στο PDF.

Ο σαρωτής εντοπίζει συνήθη παρακαμπτήρια χρώματα, όχι αυθαίρετο TeX.
Δεν πιστοποιεί το πιεστήριο: εκτελέστε επιπλέον make validate.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from generate_colors import render, validate_map, screen_hex

ROOT = Path(__file__).resolve().parent.parent
GENERATED = {'config/palette-screen.tex', 'config/palette-print2-spot.tex',
             'config/color-roles.tex', 'config/generated-assets.tex'}


def without_comments(text):
    return '\n'.join(re.split(r'(?<!\\)%', line, maxsplit=1)[0] for line in text.splitlines())


def scan_source(text, roles, authoring=False):
    """Return source-level hazards; semantic macros stay subject to PDF validation."""
    text = without_comments(text)
    # Literal documentation examples have no executable TeX commands.
    text = re.sub(r'\\texttt\{[^{}\\]*\}', '', text)
    errors = []
    for pattern, message in [
        (r'\\(?:definecolor|providecolor|colorlet|DefineNamedColor)\b', 'local color definition'),
        (r'(?:Book\w+|[A-Za-z]+)\s*!\s*\d+', 'ad-hoc color mixing'),
        (r'(?<![A-Za-z])(?:ProofRed|ProofBlack|BookPalette(?:Spot|Black))\w*', 'direct palette swatch instead of a semantic role'),
        (r'\\(?:shade|shadedraw)\b|\b(?:drop|fuzzy|circular)\s+shadow\b|\bshading\s*=', 'shading/shadow can introduce additional tones'),
        (r'\\(?:AddSpotColor|NewSpotColorSpace|SetPageColorSpace)\b', 'local printer color-space definition'),
    ]:
        if re.search(pattern,text,re.I):
            errors.append(message)
    allowed = set(roles) | {'white','none'}
    # All xcolor commands, table colors and common TikZ/tcolorbox keys.
    patterns = [
        r'\\(?:color|textcolor|pagecolor|rowcolor|cellcolor|columncolor)\s*(?:\[([^]]*)\])?\s*\{([^{}]*)\}',
        r'(?<![A-Za-z])(?:draw|fill|text|color|colback|colframe|coltitle|coltext|colupper|collower|colbacktitle|top color|bottom color|left color|right color)\s*=\s*\{?([A-Za-z][A-Za-z0-9_!.-]*)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern,text):
            if len(match.groups()) == 2:
                model, value = match.groups()
                if model:
                    errors.append('explicit color model outside generated palette')
            else:
                value = match.group(1)
            value = value.strip()
            if value and not value.startswith(('\\','#')) and value not in allowed:
                errors.append('unmanaged color: '+value)
    # Bare TikZ options can be placed anywhere in an option list, not only first.
    literal = r'(?:red|blue|orange|brown|yellow|green|cyan|magenta|gray|grey|black|purple|pink|teal|violet|olive|lime)'
    for match in re.finditer(r'\\(?:draw|fill|filldraw|path|node|addplot)\b[^\[;]*\[([^]]*)\]',text):
        if re.search(r'(?:^|,)\s*'+literal+r'(?:\s*!\s*[\d.]+)?\s*(?:,|$)',match.group(1),re.I):
            errors.append('literal TikZ color instead of a semantic role')
    for match in re.finditer(r'(?:\b(?:fill |draw |text )?opacity\s*=\s*\{?|\\(?:transparent|pgfsetfillopacity|pgfsetstrokeopacity)\s*\{)\s*([\d.]+)',text):
        try:
            if float(match.group(1)) != 1:
                errors.append('transparency introduces unapproved tones')
        except ValueError:
            errors.append('invalid opacity')
    if authoring and re.search(r'\\includegraphics\b',text):
        errors.append('direct image inclusion bypasses the asset manifest; use BookUseAsset')
    return list(dict.fromkeys(errors))


def active_sources(root, m):
    paths = set(root.glob('*.tex'))
    for directory in ['styles','config','chapters','solutions']:
        paths.update((root/directory).rglob('*.tex'))
        paths.update((root/directory).rglob('*.sty'))
    for asset in m.get('assets',{}).values():
        if asset.get('kind') == 'tex':
            paths.add(root/asset['active_path'])
    return sorted(p for p in paths if p.relative_to(root).as_posix() not in GENERATED)


def validate(root):
    m = json.loads((root/'config/color-map.json').read_text(encoding='utf-8'))
    errors = validate_map(m)
    if errors:
        return errors
    for name, value in render(m).items():
        p = root/name
        if not p.exists() or p.read_text(encoding='utf-8') != value:
            errors.append(name+': generated file out of sync; run make colors-regenerate')
    valid_assets = set()
    for name, asset in m['assets'].items():
        valid_assets.update([name,asset['active_path'],*asset.get('aliases',[])])
    for p in active_sources(root,m):
        label = str(p.relative_to(root))
        if not p.exists():
            errors.append(label+': missing active source')
            continue
        content = p.read_text(encoding='utf-8')
        authoring = p.parent == root or p.parts[-2] in {'chapters','solutions','assets'}
        errors.extend(label+': '+e for e in scan_source(content,m['semantic'],authoring))
        for match in re.finditer(r'\\BookUseAsset(?:\[[^]]*\])?\{([^{}]*)\}',without_comments(content)):
            asset = match.group(1)
            if not asset.startswith(('\\','#')) and asset not in valid_assets:
                errors.append(label+': unregistered asset '+asset)
    # Keep the declared visual structure tied to the actual callout definitions.
    style = (root/'styles/universalbook.sty').read_text(encoding='utf-8')
    for env in ['ThinkBox','AttentionBox','HistoryBox']:
        block = re.search(r'\\newtcolorbox\{%s\}.*?(?=\\newtcolorbox|\\NewDocumentEnvironment|\\newcommand\{\\BookQuote\}|\Z)' % env,style,re.S)
        if not block:
            errors.append(env+': missing environment')
            continue
        b = block.group(0)
        rule = m['visual_rules'][env]
        if 'colback='+rule['background'] not in b or 'BookCallout,' not in b:
            errors.append(env+': incorrect background/base style')
        accent = 'BookHistoryBorder' if env=='HistoryBox' else rule['accent']
        if 'borderline west={1.35pt}{0pt}{'+accent+'}' not in b:
            errors.append(env+': incorrect accent line')
    for env in ['definitionbox','theorembox']:
        block = re.search(r'\\NewDocumentEnvironment\{%s\}.*?(?=\\NewDocumentEnvironment|\\renewcommand\{\\proofname\}|\Z)' % env,style,re.S)
        if not block:
            errors.append(env+': missing environment')
            continue
        rule=m['visual_rules'][env]
        if 'borderline west={2.1pt}{0pt}{'+rule['accent']+'}' not in block.group(0) or 'colback='+rule['background'] not in block.group(0):
            errors.append(env+': incorrect accent/background')
    from PIL import Image
    # Audit the actual declared raster files, including alpha and native color mode.
    allowed_pixels = {0,255} | {int(screen_hex('000000',c['tint'])[:2],16) for c in m['colors'].values() if c['print_ink']=='BLACK'}
    for name, asset in m['assets'].items():
        p=root/asset['active_path']
        if not p.exists():
            errors.append(name+': missing active asset '+asset['active_path'])
            continue
        if asset['kind']!='raster':
            continue
        with Image.open(p) as im:
            if im.mode not in {'1','L','LA'}:
                errors.append(name+': raster must use native grayscale, not RGB/CMYK/palette')
            rgba=im.convert('RGBA')
            data=rgba.get_flattened_data() if hasattr(rgba,'get_flattened_data') else rgba.getdata()
            if any(not(r==g==b and r in allowed_pixels and a in {0,255}) for r,g,b,a in data):
                errors.append(name+': raster has an unapproved tone or partial transparency')
    return errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    try:
        errors=validate(args.root.resolve())
    except (OSError,ValueError,KeyError,TypeError) as exc:
        errors=['Cannot validate: '+str(exc)]
    if errors:
        print('FAILED: single-palette source/asset checks:')
        for error in errors:
            print(' -',error)
        return 1
    print('PASS: six swatches, shared semantic roles, generated asset registry and neutral raster art.')
    print('NOTE: Source checks are heuristic. Validate paired PDFs and confirm ink/tints/bleed with the printer.')
    return 0


if __name__=='__main__':
    sys.exit(main())
