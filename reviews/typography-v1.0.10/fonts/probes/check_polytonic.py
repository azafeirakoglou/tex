from pathlib import Path
import sys,unicodedata,subprocess,json,re,hashlib
sys.dont_write_bytecode=True
ROOT=Path('/workspace/typography-review')
sys.path.insert(0,str(ROOT))
from run_review import environment
import fitz
from fontTools.ttLib import TTFont
OUT=ROOT/'fonts/probes'
nfc='ἄνθρωπος, ἐπιστήμη, ὧν, ἀρχή'
nfd=unicodedata.normalize('NFD',nfc)
control='άνθρωπος, επιστήμη, ων, αρχή'
records={}
for label,filename in [('D_STIX','STIXTwoText-Regular.otf'),('E_LIBERTINUS','LibertinusSerif-Regular.otf')]:
 p=ROOT/'fonts/installed'/filename
 tex=(r'''\documentclass[11pt]{article}
\usepackage{fontspec}
\usepackage{polyglossia}
\setdefaultlanguage{greek}
\setmainfont{FONTFILE}[Path=FONTDIR/,Script=Default]
\newfontfamily\greekfont{FONTFILE}[Path=FONTDIR/,Script=Default]
\usepackage[paperwidth=170mm,paperheight=120mm,margin=15mm]{geometry}
\tracinglostchars=2
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{10pt}
\begin{document}
Monotonic: CONTROL

NFC: NFCWORDS

NFD: NFDWORDS
\end{document}
'''.replace('FONTFILE',filename).replace('FONTDIR',p.parent.as_posix()).replace('CONTROL',control).replace('NFCWORDS',nfc).replace('NFDWORDS',nfd))
 src=OUT/(label+'.tex');src.write_text(tex)
 command=['xelatex','-interaction=nonstopmode','-halt-on-error','-file-line-error','-output-directory='+str(OUT),str(src)]
 proc=subprocess.run(command,cwd=OUT,env=environment(),capture_output=True,text=True)
 (OUT/(label+'.build.log')).write_text(proc.stdout+proc.stderr)
 log=(OUT/(label+'.log')).read_text(errors='replace')
 missing=re.findall(r'Missing character:.*',log)
 pdf=OUT/(label+'.pdf')
 records[label]={'font_file':str(p),'font_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'xelatex_exit_code':proc.returncode,'missing_character_warnings':missing,'pdf':str(pdf),'source':str(src),'NFC_source':nfc,'NFD_source_codepoints':['U+%04X'%ord(c) for c in nfd]}
 f=TTFont(p);cmap=f.getBestCmap()
 records[label]['nfc_precomposed_missing_from_cmap']=['U+%04X'%ord(c) for c in nfc if ord(c) not in cmap and not c.isspace()]
 records[label]['nfd_missing_from_cmap']=['U+%04X'%ord(c) for c in nfd if ord(c) not in cmap and not c.isspace()]
 f.close()
 if proc.returncode==0:
  d=fitz.open(pdf);page=d[0];text=page.get_text()
  records[label]['extracted_text']=text
  records[label]['pdf_sha256']=hashlib.sha256(pdf.read_bytes()).hexdigest()
  records[label]['fonts_used']=[{'xref':x[0],'basefont':x[3],'resource':x[4]} for x in page.get_fonts()]
  records[label]['replacement_characters_in_extracted_text']=text.count('\ufffd')
  page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(OUT/(label+'.png'))
  d.close()
  records[label]['font_spans']=[{'text':s['text'],'font':s['font'],'size_pdf_bp':s['size']} for b in page.get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']] if False else []
report={'scope':'Actual XeLaTeX shaping with explicit font filenames and Script=Default, matching review Greek family; only font-probe files created. NFC/NFD forms of same polytonic words plus monotonic control.','results':records}
(OUT/'POLYTONIC_PROBE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
for k,v in records.items(): print(k,'exit',v['xelatex_exit_code'],'missingwarnings',len(v['missing_character_warnings']),'extracted',repr(v.get('extracted_text')))
