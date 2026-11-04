from pathlib import Path
import json,datetime,hashlib,re,unicodedata
import fitz
from fontTools.ttLib import TTFont
ROOT=Path('/workspace/tex')
OUT=Path('/workspace/typography-review/reports')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pt(bp):return round(bp*72.27/72,6)
fontpaths={
 'Inter-Regular':ROOT/'.local/fonts/Inter-Regular.otf',
 'Inter-Medium':ROOT/'.local/fonts/Inter-Medium.otf',
 'Inter-SemiBold':ROOT/'.local/fonts/Inter-SemiBold.otf',
 'NotoSerif-Regular':ROOT/'.local/fonts/NotoSerif-Regular.ttf',
 'NotoSerif-Medium':ROOT/'.local/fonts/NotoSerif-Medium.ttf',
 'STIXTwoMath-Regular':ROOT/'.local/fonts/STIXTwoMath-Regular.ttf',
}
metrics={}
for name,p in fontpaths.items():
 f=TTFont(p)
 os2=f['OS/2']
 row={'path':str(p),'sha256':sha(p),'units_per_em':f['head'].unitsPerEm,'weight_class':os2.usWeightClass,'x_height_units':getattr(os2,'sxHeight',None),'cap_height_units':getattr(os2,'sCapHeight',None)}
 if 'MATH' in f:
  c=f['MATH'].table.MathConstants
  row['MATH']={'script_percent':c.ScriptPercentScaleDown,'scriptscript_percent':c.ScriptScriptPercentScaleDown,'display_operator_min_height_units':c.DisplayOperatorMinHeight,'axis_height_units':c.AxisHeight.Value}
 metrics[name]=row
samples={}
for edition in ['SCREEN','PRINT']:
 path=ROOT/f'releases/v1.0.10/Starter_v1.0.10_{edition}.pdf'
 doc=fitz.open(path); page=doc[3]
 lines=[]
 for b in page.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   if l['bbox'][1]<230:
    lines.append([{'text':s['text'],'font':s['font'],'size_pdf_bp':round(s['size'],6),'size_tex_pt':pt(s['size']),'origin_pdf_bp':[round(n,6) for n in s['origin']]} for s in l['spans']])
 first=next(l[0] for l in lines if l[0]['text'].startswith('Η θέση ενός σώματος'))
 second=next(l[0] for l in lines if l[0]['text'].startswith('Για κίνηση από τη θέση'))
 body_gap=second['origin_pdf_bp'][1]-first['origin_pdf_bp'][1]
 think=[l[0] for l in lines if l[0]['text'].startswith(('Επιλέγω τη θετική','αρχική από την τελική','τόπισης.'))]
 samples[edition]={'path':str(path),'sha256':sha(path),'page_number_physical':4,'media_box_mm':[round(page.rect.width*25.4/72,4),round(page.rect.height*25.4/72,4)],'body_first_two_baseline_gap_pdf_bp':round(body_gap,6),'body_first_two_baseline_gap_tex_pt':pt(body_gap),'think_body_adjacent_baseline_gaps_tex_pt':[pt(b['origin_pdf_bp'][1]-a['origin_pdf_bp'][1]) for a,b in zip(think,think[1:])],'spans':lines}
review={
 'status':'recorded-before-experimental-typesetting',
 'recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'stable_version':'1.0.10',
 'inspection_only':True,
 'stable_source_writes':False,
 'files_inspected':['config/book-config.tex','styles/universalbook.sty','styles/book-callouts.tex','main.tex','main-print2.tex','starter.tex','chapters/starter-chapter.tex','chapters/demo-physics.tex','chapters/demo-math.tex','docs/AUTHORING.md','docs/CALLOUT_ICONS.md'],
 'source_sha256':{n:sha(ROOT/n) for n in ['config/book-config.tex','styles/universalbook.sty','styles/book-callouts.tex','main.tex','main-print2.tex']},
 'document':{'class':'book','class_options':['11pt','twoside','openright'],'nominal_body_size_tex_pt':11,'actual_normalsize_tex_pt':10.95,'page_mm':[170,240],'margins_mm':{'inner':20,'outer':17,'top':19,'bottom':20},'text_width_mm':133,'text_height_mm':201,'two_column_gutter_mm':6},
 'font_roles':{'body_regular':'Inter Regular','body_bold':'Inter SemiBold','body_italic':'Inter Italic','body_bold_italic':'Inter SemiBold Italic','heading_regular':'Noto Serif Regular','heading_bfseries':'Noto Serif Medium','heading_italic':'Noto Serif Italic','heading_bfseries_italic':'Noto Serif Medium Italic','math':'STIX Two Math Regular','callout_label_and_solution':'Inter Medium','monospace':'DejaVu Sans Mono','greek_body_font':'Inter via explicit greekfont and greekfontsf, Script=Default'},
 'sizes_tex_pt':{'body':10.95,'inline_math_normal':10.95,'display_math_normal':10.95,'equation_tag_normal':10.95,'math_script_normal':7.665,'math_scriptscript_normal':6.0225,'small_body_and_math':10,'math_script_small':7,'math_scriptscript_small':5.5,'section':12.5,'subsection':10.5,'minor_heading':11,'major_thematic_band':11.7,'question_subcategory_heading':10.1,'worked_example_title':10.4,'solution_label':10.2,'callout_heading':9.2,'callout_body':10,'running_header':8,'figure_label':9,'figure_tick':8,'caption':9.1,'opening_goals_body':10.2,'opening_goals_heading':14},
 'leading_and_spacing':{
  'baselinestretch':1.10,'normalsize_declared_baselineskip_tex_pt':13.6,'normalsize_effective_baselineskip_tex_pt_computed':14.96,
  'small_declared_baselineskip_tex_pt':12,'small_effective_baselineskip_tex_pt_computed':13.2,
  'worked_example_title_declared_leading_tex_pt':13.5,'callout_heading_declared_leading_tex_pt':11.5,'solution_label_declared_leading_tex_pt':13,
  'parskip':'3.7pt plus 1.1pt minus .6pt','parindent_tex_pt':0,'emergencystretch_em':2,'widowpenalty':10000,'clubpenalty':10000,'interlinepenalty':50,'raggedbottom':True,
  'normal_display_skips_from_size11_clo':{'above_and_below':'11pt plus 3pt minus 6pt','above_short':'0pt plus 3pt','below_short':'6.5pt plus 3.5pt minus 3pt'},
  'small_display_skips_from_size11_clo':{'above_and_below':'10pt plus 2pt minus 5pt','above_short':'0pt plus 3pt','below_short':'6pt plus 3pt minus 3pt'},
  'leading_note':'Declared font leading is multiplied by baselinestretch on font selection. PDF baseline measurements below verify ordinary normal/small paragraphs; math height/depth can force extra interline spacing in other paragraphs.'},
 'math_setup':{
  'engine':'XeLaTeX','package':'unicode-math','setmathfont':'STIXTwoMath-Regular.ttf','explicit_scale':None,'effective_scale':1.0,'explicit_DeclareMathSizes_override':False,
  'default_math_style':'TeX (unicode-math package default, no project override)','normal_Latin_variables':'italic uppercase and lowercase','normal_Greek_variables':'uppercase upright, lowercase italic','bold_style':'TeX default: Latin upright bold; uppercase Greek upright bold; lowercase Greek italic bold','partial':'italic','nabla':'upright',
  'scripts':'Font MATH constants:70% script,55% scriptscript; same ratios at normal and small contexts.','inline_vs_display':'Same base font size. Displaystyle changes fractions, operator sizes, limits and spacing.','equation_numbering':'book chapter.equation, amsmath tag rendering in normal text font; no project tagform/maketag or tag font override found.','units':'Explicit \\mathrm and \\text in samples; Greek text handled by Polyglossia.'},
 'callouts':{
  'shared_construction':'BookCalloutRender plus BookCalloutDecoration per environment; first-piece-only icons',
  'heading_font':'Inter Medium9.2pt','body_font':'Inter Regular10pt','icon_outline_tex_pt':1.08,
  'ThinkBox':{'surface':'none, page shows','decoration':'two vector brackets','bracket_width_tex_pt':1.08,'bracket_arms_mm':3,'bracket_inset_mm':0.5,'accent':'Second ink100%','body':'Black100%'},
  'AttentionBox':{'background':'Second ink10%','left_rule_tex_pt':2,'other_border_tex_pt':0.35,'accent':'Second ink100%'},
  'HistoryBox':{'background':'Black10%','left_rule_tex_pt':2,'other_border_tex_pt':0.35,'accent':'Second ink100%'},
  'ProblemBox':{'background':'Black10%','title_background':'paper white','border_and_title_divider':'Black55%,0.35pt','title_font':'Noto Serif Medium10.4pt','title_dot_mm':2,'title_dot_gap_mm':1.6,'body_font':'Inter Regular10pt','solution_label':'Inter Medium10.2pt'}},
 'font_file_metrics':metrics,
 'actual_pdf_samples':samples,
 'limitations':['No new TeX was compiled for this baseline. Display skip values are source/class declarations, not one universal measured gap: paragraph length, math height and page glue affect actual distances.','TeX pt and PDF bp differ by72.27/72; size values here normalize PDF spans toTeX pt.','MathScriptScript size calculated from actual font MATH55% constant; starter excerpt contains first-level scripts but no nested script sample.'],
}
(OUT/'BASELINE_TYPOGRAPHY.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print('BASELINE_READY',OUT/'BASELINE_TYPOGRAPHY.json')
print('Measured normal baseline gaps TeXpt:',{k:v['body_first_two_baseline_gap_tex_pt'] for k,v in samples.items()})
print('Measured small baseline gaps TeXpt:',{k:v['think_body_adjacent_baseline_gaps_tex_pt'] for k,v in samples.items()})
