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


def command_arguments(text, command, arity):
    """Read literal braced arguments with nesting, skipping command definitions."""
    matches=[]
    for match in re.finditer(r'\\'+re.escape(command)+r'\b',text):
        pos=match.end()
        args=[]
        for _ in range(arity):
            while pos<len(text) and text[pos].isspace():
                pos+=1
            if pos>=len(text) or text[pos]!='{':
                break
            depth=1
            first=pos+1
            pos+=1
            while pos<len(text) and depth:
                if text[pos]=='{' and (pos==0 or text[pos-1]!='\\'):
                    depth+=1
                elif text[pos]=='}' and (pos==0 or text[pos-1]!='\\'):
                    depth-=1
                pos+=1
            if depth:
                break
            args.append(text[first:pos-1])
        if len(args)==arity:
            matches.append(args)
    return matches


def braced_key_value(text, key):
    """Read a literal braced pgf key value, including nested TeX arguments."""
    text=re.sub(r'\s+','',text)
    match=re.search(re.escape(re.sub(r'\s+','',key))+'=',text)
    if not match:
        return None
    values=command_arguments('\\ReadValue'+text[match.end():],'ReadValue',1)
    return values[0][0] if values else None


def validate_callouts(root,m):
    """Check delegation and role declarations, rather than duplicated box bodies."""
    path=root/'styles/book-callouts.tex'
    if not path.exists():
        return ['Callouts: missing shared styles/book-callouts.tex']
    text=without_comments(path.read_text(encoding='utf-8'))
    style=without_comments((root/'styles/universalbook.sty').read_text(encoding='utf-8'))
    errors=[]
    if r'\input{styles/book-callouts.tex}' not in re.sub(r'\s+','',style):
        errors.append('Callouts: shared construction is not loaded by universalbook.sty')
    expected={
        'AttentionBox':('BookDeclareCallout',r'\BookCalloutWarning',r'\LabelAlert'),
        'ThinkBox':('BookDeclareCallout',r'\BookCalloutBulb',r'\LabelThink'),
        'HistoryBox':('BookDeclareTitledCallout',r'\BookCalloutHourglass',r'\LabelHistory'),
    }
    declarations={}
    for command in ['BookDeclareCallout','BookDeclareTitledCallout']:
        for env,bg,accent,icon,title in command_arguments(text,command,5):
            if env not in expected:
                errors.append('Callouts: undeclared visual rules for '+env)
                continue
            if env in declarations:
                errors.append(env+': duplicate callout declaration')
            declarations[env]=(command,bg,accent,icon,title)
    for env,(command,icon,title) in expected.items():
        rule=m['visual_rules'][env]
        wanted=(command,rule['background'],rule['accent'],icon,title)
        if declarations.get(env)!=wanted:
            errors.append(env+': must use the shared factory with its registered roles/icon/title')
    # Reject private redefinitions which would escape the shared renderer.
    direct=r'\\(?:newtcolorbox|renewtcolorbox|newenvironment|renewenvironment|NewDocumentEnvironment|RenewDocumentEnvironment)\s*\{(AttentionBox|ThinkBox|HistoryBox)\}'
    for p in active_sources(root,m):
        if p.exists() and re.search(direct,without_comments(p.read_text(encoding='utf-8'))):
            errors.append(str(p.relative_to(root))+': direct callout definition bypasses shared construction')
    # One renderer owns background/title/first-fragment icons. Each registered
    # v1.0.12 decoration supplies exactly one west rule after clearing frames.
    compact=re.sub(r'\s+','',text)
    required=[
        'BookCalloutRender/.stylenargs={5}{BookCallout,',
        'colback=#1',
        'noborderline',
        r'beforeupper={\BookCalloutHeading{#2}{#4}{#5}}',
        r'overlayunbroken={\BookCalloutCenteredIcon{#3}}',
        r'overlayfirst={\BookCalloutCenteredIcon{#3}}',
    ]
    if any(part not in compact for part in required):
        errors.append('Callouts: common background/rule/title/first-piece icon pipeline is incomplete')
    # Verify both public-signature wrappers actually delegate to that renderer.
    wrappers={}
    pattern=r'\\newcommand\s*\{\\(BookDeclare(?:Titled)?Callout)\}\s*\[5\]\s*'
    for match in re.finditer(pattern,text):
        tail=text[match.end():]
        bodies=command_arguments('\\ReadBody'+tail,'ReadBody',1)
        if bodies:
            wrappers[match.group(1)]=re.sub(r'\s+','',bodies[0][0])
    for command in ['BookDeclareCallout','BookDeclareTitledCallout']:
        body=wrappers.get(command,'')
        if 'BookCalloutRender=' not in body:
            errors.append('Callouts: factory '+command+' must delegate to the common renderer')
        dispatch='BookCalloutDecoration/#1'
        if dispatch not in body or body.find(dispatch)<body.find('BookCalloutRender='):
            errors.append('Callouts: factory '+command+' must apply its registered decoration after the common renderer')
    if r'\newtcolorbox{#1}{' not in wrappers.get('BookDeclareCallout',''):
        errors.append('Callouts: plain environments must retain their no-argument signature')
    if r'\newtcolorbox{#1}[1][]' not in wrappers.get('BookDeclareTitledCallout',''):
        errors.append('Callouts: HistoryBox must retain its optional-title signature')
    # A decoration can suppress the inherited frame/fill without replacing the
    # shared title and first-piece-only icon pipeline. Check its selected variant,
    # not incidental drawing dimensions, which remain configurable in TeX.
    for env in expected:
        rule=m['visual_rules'][env]
        decoration=braced_key_value(text,'BookCalloutDecoration/'+env+'/.style')
        if decoration is None:
            errors.append(env+': missing registered callout decoration')
            continue
        # Decorations can change geometry, but may not take over the shared
        # title and first-fragment icon pipeline (including through key suffixes
        # such as "overlay first app").
        if 'overlay' in decoration:
            errors.append(env+': decoration must retain the shared first-piece-only icon overlays')
        if rule.get('decoration')!='accent-rule':
            errors.append(env+': unsupported callout decoration; expected the registered single west rule')
            continue
        # Widths differ geometrically, but all colours and surfaces must stay
        # registered. A missing or substituted west rule is never accepted.
        wanted=(r'\BookAttentionRuleWidth' if env=='AttentionBox'
                else r'\BookStableCalloutRuleWidth')
        west_args=command_arguments('\\ReadRule'+decoration[
            decoration.find('borderlinewest=')+len('borderlinewest='):],
            'ReadRule',3) if 'borderlinewest=' in decoration else []
        if ('noborderline' not in decoration.split(',')
                or decoration.count('borderlinewest=')!=1
                or west_args!=[[wanted,'0pt',rule['accent']]]):
            errors.append(env+': accent-rule decoration must replace the inherited perimeter with its registered west rule')
        # A single west rule applies through tcolorbox's complete breakable
        # pipeline. Custom underlays, other sides, or a replacement fill would
        # escape that pipeline and are forbidden, including fragment suffixes.
        if ('colback' in decoration or 'colframe' in decoration
                or 'borderline=' in decoration or 'borderlineeast' in decoration
                or 'borderlinenorth' in decoration or 'borderlinesouth' in decoration
                or 'underlay' in decoration):
            errors.append(env+': accent-rule decoration must preserve the common fill and only draw its west rule')
        if env=='ThinkBox':
            if (rule.get('surface')!='none'
                    or rule['background']!=m.get('white','white')
                    or 'interiorhidden' not in decoration.split(',')):
                errors.append(env+': unfilled west-rule decoration must suppress the inherited frame and fill')
        elif 'interiorhidden' in decoration:
            errors.append(env+': accent-rule decoration must preserve the common fill')
    return errors


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
    # All three callouts must delegate to the one shared construction pipeline.
    errors.extend(validate_callouts(root,m))
    style = (root/'styles/universalbook.sty').read_text(encoding='utf-8')
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
