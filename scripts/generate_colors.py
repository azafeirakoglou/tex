#!/usr/bin/env python3
"""Μία παλέτα/αντιστοίχιση ρόλων → PRINT, SCREEN και μητρώο εικαστικών.

Τα ποσοστά δηλώνουν κάλυψη μελανιού. Η SCREEN αναμειγνύει το βασικό
μπλε με λευκό σε κωδικοποιημένο sRGB· δεν προσομοιώνει χρώμα πιεστηρίου.
"""
from decimal import Decimal, ROUND_HALF_UP
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {f'{prefix}{tint}': (ink, tint)
            for prefix, ink in [('Spot', 'SECOND'), ('Black', 'BLACK')]
            for tint in [100, 55, 10]}


def screen_hex(base, tint):
    """Deterministic nearest-integer white mix, with halves rounded upwards."""
    fraction = Decimal(str(tint)) / 100
    return ''.join(f'{int((Decimal(int(base[i:i+2],16))*fraction + 255*(1-fraction)).quantize(Decimal(1), rounding=ROUND_HALF_UP)):02X}'
                   for i in [0, 2, 4])


def validate_map(m):
    errors = []
    def require(ok, message):
        if not ok:
            errors.append(message)
    require(m.get('schema_version') == 3, 'schema_version must be 3')
    require(m.get('authoritative_edition') == 'PRINT', 'PRINT must remain authoritative')
    require(set(m.get('colors', {})) == set(EXPECTED), 'Exactly the six Spot/Black 100/55/10 swatches are required')
    for name, (ink, tint) in EXPECTED.items():
        val = m.get('colors', {}).get(name, {})
        require(val.get('print_ink') == ink and val.get('tint') == tint, name + ': incorrect ink/tint')
        require('screen_hex' not in val, name + ': SCREEN tint must be derived from its base, not supplied separately')
    bases = m.get('screen_base_hex', {})
    require(set(bases) == {'SECOND', 'BLACK'}, 'Exactly two SCREEN base inks are required')
    for ink, value in bases.items():
        require(isinstance(value,str) and re.fullmatch(r'[0-9A-F]{6}', value), ink + ': invalid SCREEN base HEX')
    require(bases.get('BLACK') == '000000', 'SCREEN black must stay neutral black')
    require(bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', m.get('spot_ink_name',''))), 'Invalid PDF spot ink name')
    alternate = m.get('spot_alternate_cmyk', [])
    require(isinstance(alternate,list) and len(alternate)==4 and all(type(v) in (int,float) and 0 <= v <= 1 for v in alternate), 'Spot alternate CMYK must contain four numbers from 0 to 1')
    for name, value in m.get('semantic', {}).items():
        require(bool(re.fullmatch(r'Book[A-Za-z]+', name)), 'Invalid semantic color role: ' + name)
        require(isinstance(value,str) and value in EXPECTED, name + ': select one canonical swatch')
    require(bool(m.get('semantic')), 'Semantic roles are missing')
    aliases = set()
    for name, asset in m.get('assets', {}).items():
        require(bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name)), 'Invalid asset ID: ' + name)
        require(asset.get('kind') in {'raster','tex'}, name + ': kind must be raster or tex')
        path = asset.get('active_path','')
        require(bool(re.fullmatch(r'[A-Za-z0-9_./-]+',path)) and not Path(path).is_absolute() and '..' not in Path(path).parts, name + ': invalid asset path')
        for alias in [name, path, *asset.get('aliases', [])]:
            require(isinstance(alias,str) and bool(re.fullmatch(r'[A-Za-z0-9_./-]+',alias)), name + ': unsafe alias')
            require(alias not in aliases, name + ': duplicate asset alias ' + alias)
            aliases.add(alias)
    return errors


def render(m):
    errors = validate_map(m)
    if errors:
        raise ValueError('\n'.join(errors))
    screen = ['% AUTO-GENERATED v0.33. Πηγή: config/color-map.json.',
              '% Μία βασική μπλε τιμή + τα ίδια ποσοστά μελανιού της PRINT.']
    alternate = ' '.join(f'{v:g}' for v in m['spot_alternate_cmyk'])
    pr = ['% AUTO-GENERATED v0.33. PRINT = κύρια έκδοση, τεχνικό δοκίμιο.',
          '% Το spot μελάνι και τα ποσοστά απαιτούν επιβεβαίωση τυπογραφείου.',
          r'\NewSpotColorSpace{BookTwoInk}',
          r'\AddSpotColor{BookTwoInk}{Second}{%s}{%s}' % (m['spot_ink_name'], alternate),
          r'\SetPageColorSpace{BookTwoInk}']
    for name, value in m['colors'].items():
        screen.append(r'\definecolor{BookPalette%s}{HTML}{%s}' % (name, screen_hex(m['screen_base_hex'][value['print_ink']], value['tint'])))
        if value['print_ink'] == 'SECOND':
            pr.append(r'\definecolor{BookPalette%s}{spotcolor}{Second,%g}' % (name, value['tint']/100))
        else:
            pr.append(r'\definecolor{BookPalette%s}{gray}{%g}' % (name, 1-value['tint']/100))
    roles = ['% AUTO-GENERATED v0.33. Κοινοί χρωματικοί ρόλοι PRINT/SCREEN.']
    roles.extend(r'\colorlet{%s}{BookPalette%s}' % (name,value) for name,value in m['semantic'].items())
    assets = ['% AUTO-GENERATED v0.33. Μητρώο κοινών εικαστικών PRINT/SCREEN.']
    for name, asset in m['assets'].items():
        assets.append(r'\BookDeclareAsset{%s}{%s}{%s}' % (name,asset['active_path'],asset['kind']))
        for alias in asset.get('aliases', []):
            assets.append(r'\BookDeclareAssetAlias{%s}{%s}' % (alias,name))
    return {name:'\n'.join(lines)+'\n' for name,lines in [
        ('config/palette-screen.tex',screen), ('config/palette-print2-spot.tex',pr),
        ('config/color-roles.tex',roles), ('config/generated-assets.tex',assets)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Check generated files without writing')
    args = parser.parse_args()
    try:
        generated = render(json.loads((ROOT/'config/color-map.json').read_text(encoding='utf-8')))
    except (ValueError,KeyError,TypeError) as exc:
        print('INVALID COLOR MAP:',exc,file=sys.stderr)
        return 1
    changed = False
    for file, value in generated.items():
        path = ROOT/file
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != value:
                print('OUT OF SYNC',file)
                changed = True
            else:
                print('OK',file)
        else:
            path.write_text(value,encoding='utf-8')
            print('WROTE',file)
    return int(changed)


if __name__ == '__main__':
    sys.exit(main())
