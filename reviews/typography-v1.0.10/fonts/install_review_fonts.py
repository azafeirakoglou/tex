from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.request, hashlib, zipfile, json, datetime, unicodedata, sys
sys.dont_write_bytecode=True
from fontTools.ttLib import TTFont
ROOT=Path(__file__).resolve().parent
install=ROOT/'installed'; download=ROOT/'downloads'; license_dir=ROOT/'licenses'
for p in [install,download,license_dir]: p.mkdir(exist_ok=True)
commit='744a22a4dd626cd14d75728aef34fc8ad7c85db0'
base=f'https://raw.githubusercontent.com/stipub/stixfonts/{commit}/'
styles=['Regular','Italic','Medium','MediumItalic','SemiBold','SemiBoldItalic','Bold','BoldItalic']
urls=[(f'STIXTwoText-{style}.otf',base+f'fonts/static_otf/STIXTwoText-{style}.otf') for style in styles]
def fetch(pair):
 name,url=pair
 with urllib.request.urlopen(url,timeout=45) as r: data=r.read()
 (install/name).write_bytes(data)
 return name,{'url':url,'upstream_repository':'https://github.com/stipub/stixfonts','upstream_commit':commit,'release_tag':'v2.13b171','installation':'official static OTF, unmodified','sha256':hashlib.sha256(data).hexdigest()}
records=dict(ThreadPoolExecutor(max_workers=6).map(fetch,urls))
with urllib.request.urlopen(base+'OFL.txt',timeout=30) as r: (license_dir/'STIXTwoText-OFL.txt').write_bytes(r.read())
libzip=download/'Libertinus-7.051.zip'
with zipfile.ZipFile(libzip) as z:
 for style in ['Regular','Italic','Semibold','SemiboldItalic','Bold','BoldItalic']:
  name=f'LibertinusSerif-{style}.otf'
  data=z.read('Libertinus-7.051/static/OTF/'+name)
  (install/name).write_bytes(data)
  records[name]={'url':'https://github.com/alerque/libertinus/releases/download/v7.051/Libertinus-7.051.zip','archive_member':'Libertinus-7.051/static/OTF/'+name,'archive_sha256':hashlib.sha256(libzip.read_bytes()).hexdigest(),'upstream_repository':'https://github.com/alerque/libertinus','upstream_commit':'9c31f8b436b8ea33dccffbca3972a88d5ff75b0f','release_tag':'v7.051','installation':'official static OTF, unmodified','sha256':hashlib.sha256(data).hexdigest()}
 name='LibertinusMath-Regular.otf'; data=z.read('Libertinus-7.051/static/OTF/'+name)
 (install/name).write_bytes(data)
 records[name]={'url':'https://github.com/alerque/libertinus/releases/download/v7.051/Libertinus-7.051.zip','archive_member':'Libertinus-7.051/static/OTF/'+name,'archive_sha256':hashlib.sha256(libzip.read_bytes()).hexdigest(),'upstream_repository':'https://github.com/alerque/libertinus','upstream_commit':'9c31f8b436b8ea33dccffbca3972a88d5ff75b0f','release_tag':'v7.051','installation':'official static OTF, unmodified','sha256':hashlib.sha256(data).hexdigest()}
 (license_dir/'Libertinus-OFL.txt').write_bytes(z.read('Libertinus-7.051/OFL.txt'))
modern='ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρστυφχψωςΆΈΉΊΌΎΏάέήίόύώΪΫϊϋΐΰ'
extended=[cp for cp in range(0x1f00,0x2000) if unicodedata.category(chr(cp))!='Cn']
mathgreek='ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρστυφχψωϑϕϖϱϰϵ'
mathitalic_greek=[cp for cp in range(0x1d6e2,0x1d71c) if unicodedata.category(chr(cp))!='Cn']
def named(f,ident):
 for platform,encoding,lang in [(3,1,0x409),(3,10,0x409),(1,0,0)]:
  x=f['name'].getName(ident,platform,encoding,lang)
  if x:return x.toUnicode()
 for x in f['name'].names:
  if x.nameID==ident:return x.toUnicode()
 return None
for name,r in records.items():
 p=install/name; f=TTFont(p); cmap=f.getBestCmap(); os2=f['OS/2']; upem=f['head'].unitsPerEm
 r.update({'file':str(p),'family':named(f,1),'subfamily':named(f,2),'typographic_family':named(f,16),'typographic_subfamily':named(f,17),'postscript_name':named(f,6),'font_version':named(f,5),'weight_class':os2.usWeightClass,'units_per_em':upem,'x_height_units':getattr(os2,'sxHeight',None),'x_height_em':getattr(os2,'sxHeight',0)/upem,'cap_height_em':getattr(os2,'sCapHeight',0)/upem,'ascender_em':os2.sTypoAscender/upem,'descender_em':os2.sTypoDescender/upem,'typo_line_gap_em':os2.sTypoLineGap/upem,'is_variable':'fvar' in f,'has_MATH_table':'MATH' in f,'modern_greek_characters_tested':len(set(modern)),'modern_greek_missing':['U+%04X'%ord(ch) for ch in sorted(set(modern)) if ord(ch) not in cmap],'greek_extended_assigned_tested':len(extended),'greek_extended_assigned_missing':['U+%04X'%cp for cp in extended if cp not in cmap],'math_greek_missing':['U+%04X'%ord(ch) for ch in sorted(set(mathgreek)) if ord(ch) not in cmap],'math_italic_greek_missing':['U+%05X'%cp for cp in mathitalic_greek if cp not in cmap]})
 if 'MATH' in f:
  constants=f['MATH'].table.MathConstants
  r['math_constants']={'ScriptPercentScaleDown':constants.ScriptPercentScaleDown,'ScriptScriptPercentScaleDown':constants.ScriptScriptPercentScaleDown}
 f.close()
manifest={'status':'ready','created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Review-local font files only; no system or stable installation modified. No variable instantiation or glyph modification.','fonts':records,'licenses':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(license_dir.iterdir()) if p.is_file()},'recommendations':{'D':{'body_regular':'STIXTwoText-Regular.otf','body_italic':'STIXTwoText-Italic.otf','body_bold':'STIXTwoText-SemiBold.otf','body_bold_italic':'STIXTwoText-SemiBoldItalic.otf','heading_regular':'STIXTwoText-Regular.otf','heading_bold':'STIXTwoText-Medium.otf','heading_italic':'STIXTwoText-Italic.otf','heading_bold_italic':'STIXTwoText-MediumItalic.otf','medium_labels':'STIXTwoText-Medium.otf','math':'Retain stable STIXTwoMath-Regular.ttf unchanged'},'E':{'body_regular':'LibertinusSerif-Regular.otf','body_italic':'LibertinusSerif-Italic.otf','body_bold':'LibertinusSerif-Semibold.otf','body_bold_italic':'LibertinusSerif-SemiboldItalic.otf','heading_regular':'LibertinusSerif-Regular.otf','heading_bold':'LibertinusSerif-Semibold.otf','heading_italic':'LibertinusSerif-Italic.otf','heading_bold_italic':'LibertinusSerif-SemiboldItalic.otf','medium_labels':'LibertinusSerif-Semibold.otf','math':'LibertinusMath-Regular.otf'}},'notes':['STIX Two Text official release tag v2.13b171 supplies static Medium and SemiBold faces; no synthesized weight required.','Libertinus Serif has genuine Semibold (600), not a Medium (500) face. Using Semibold for emphasized headings/labels is an explicit weight difference.','Downloads/source archives may be excluded from delivery ZIP; installed fonts and OFL licenses are sufficient for reproduction.']}
(ROOT/'FONT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
for name in ['STIXTwoText-Regular.otf','STIXTwoText-Medium.otf','LibertinusSerif-Regular.otf','LibertinusSerif-Semibold.otf','LibertinusMath-Regular.otf']:
 r=records[name]
 print(name,r['family'],r['subfamily'],'weight',r['weight_class'],'xheight',r['x_height_em'],'modernmissing',len(r['modern_greek_missing']),'polytonicmissing',len(r['greek_extended_assigned_missing']),'MATH',r['has_MATH_table'])
print('Manifest ready',ROOT/'FONT_MANIFEST.json','installedfiles',len(records))
