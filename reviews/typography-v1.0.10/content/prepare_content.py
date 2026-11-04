from pathlib import Path
import json, hashlib
ROOT=Path('/workspace/tex')
OUT=Path('/workspace/typography-review/content')
provenance=[]
def take(path,start,end):
    lines=(ROOT/path).read_text().splitlines()
    selected='\n'.join(lines[start-1:end])+'\n'
    text='\n'.join(line for line in selected.splitlines() if not line.lstrip().startswith('%'))+'\n'
    provenance.append({'source':path,'lines':[start,end],'source_excerpt_sha256':hashlib.sha256(selected.encode()).hexdigest(),'transformation':'Comment-only lines omitted; visible text and math retained.'})
    return '% Source: '+path+':'+str(start)+'-'+str(end)+'\n'+text
parts=[]
parts.append(r'''% Identical five-page content for all typography variants, v1.0.10 review.
% Reuses stable authoring commands; no geometry, color or style redefinitions.
\setcounter{chapter}{1}
\setcounter{section}{0}
\setcounter{equation}{0}
\setcounter{figure}{0}
\setcounter{workedexample}{0}
\setcounter{page}{1}
\BookRememberRunningChapter{Κίνηση σε μία διάσταση}
\markboth{Κίνηση σε μία διάσταση}{Κίνηση σε μία διάσταση}

% PAGE 1 — Physics theory and inline math.
\BookSection{Θεωρία}
\section{Περιγραφή της κίνησης}
''')
parts.append(take('chapters/demo-physics.tex',19,19))
parts.append(take('chapters/starter-chapter.tex',12,17))
parts.append(take('chapters/demo-assessment.tex',25,27))
parts.append(take('chapters/demo-physics.tex',24,26))
parts.append(r'\BookMinorHeading{Από το διάγραμμα στη φυσική ερμηνεία}'+'\n')
parts.append(take('chapters/demo-physics.tex',42,42))
parts.append(take('stress-content.tex',5,9).replace('τους.','τους.',1).replace('αποτελέσματος. Η τελική απάντηση περιλαμβάνει κατάλληλη\nμονάδα και σύντομη αιτιολόγηση.\\par}','αποτελέσματος. Η τελική απάντηση περιλαμβάνει κατάλληλη\nμονάδα και σύντομη αιτιολόγηση.\\par'))
parts.append(take('stress-content.tex',13,14))
parts.append(r'''
\clearpage
% PAGE 2 — Both worked examples, including their original callouts.
\BookSection{Λυμένα παραδείγματα}
''')
parts.append(take('chapters/demo-physics.tex',115,143))
parts.append(r'''
\clearpage
% PAGE 3 — Dense math plus explicitly marked missing-operator diagnostics.
\BookSection{Μαθηματικοί συμβολισμοί}
\section{Η συνάρτηση πρώτου βαθμού}
''')
parts.append(take('chapters/demo-math.tex',16,16))
parts.append(take('stress-content.tex',379,386))
parts.append(take('chapters/demo-math.tex',18,20))
parts.append(r'''
\BookMinorHeading{Συμπληρωματική τυπογραφική δοκιμή}
Οι επόμενες σχέσεις προστίθενται μόνο για τον έλεγχο ριζών, αθροισμάτων,
διαδοχικών δεικτών και ελληνικών χαρακτήρων.
\begin{align*}
 \sqrt{x^2+y^2}&=\sqrt{\frac{a^2+b^2}{1+t^2}}, &
 S_n&=\sum_{k=1}^{n}\frac{1}{k^2},\\
 x_{i_j}^{\,2}&=\frac{a_{i+1}-a_i}{\Delta t}, &
 \vec F&=m\vec a.
\end{align*}
Λατινικά: $a,\allowbreak b,\allowbreak c,\allowbreak x,\allowbreak y,\allowbreak z,\allowbreak A,\allowbreak B,\allowbreak F,\allowbreak N$.
Ελληνικά: $\alpha,\allowbreak \beta,\allowbreak \gamma,\allowbreak \delta,\allowbreak \theta,\allowbreak \lambda,\allowbreak \mu,\allowbreak \nu,\allowbreak \pi,\allowbreak \rho,\allowbreak \sigma,\allowbreak 
\tau,\allowbreak \phi,\allowbreak \varphi,\allowbreak \chi,\allowbreak \psi,\allowbreak \omega,\allowbreak \Gamma,\allowbreak \Delta,\allowbreak \Theta,\allowbreak \Sigma,\allowbreak \Omega$.

Δοκιμή χημικής γραφής: $\mathrm{H_2O}$, $\mathrm{H_2SO_4}$,
$\mathrm{Na^+}$, $\mathrm{SO_4^{2-}}$ και $10^{-3}\,\mathrm{mol\,L^{-1}}$.
Ζεύγη σύγκρισης: $\nu/v$, $\rho/p$, $\mu/u$ και $\alpha/a$.

\clearpage
% PAGE 4 — Standard callouts, including dense inline math in a small context.
\BookSection{Διδακτικά κουτιά}
\section{Επιλογή σχέσης και έλεγχος}
''')
parts.append(take('stress-content.tex',5,9).replace('αιτιολόγηση.\\par}','αιτιολόγηση.\\par'))
parts.append(take('chapters/demo-physics.tex',38,40))
parts.append(take('chapters/demo-physics.tex',138,140))
parts.append(take('chapters/demo-math.tex',57,59))
parts.append(r'''
\begin{ThinkBox}
Συμπληρωματική τυπογραφική δοκιμή μέσα στο κουτί:
για $r=\sqrt{x^2+y^2}$, $q=\frac{a_{i+1}-a_i}{\Delta t}$ και
$S_n=\sum_{k=1}^{n}\frac{1}{k^2}$, εξετάζουμε τους δείκτες, τα κλάσματα
και την απόσταση των διαδοχικών γραμμών. Οι $\alpha$, $\beta$ και $\upsilon$
παραμένουν ευδιάκριτες από τα λατινικά $a$, $b$ και $v$.
\end{ThinkBox}

\clearpage
% PAGE 5 — Actual stable TikZ geometry and math labels.
\BookSection{Διαγράμματα και σύμβολα}
\section{Θέση, μετατόπιση και χρόνος}
''')
parts.append(r'\begin{center}'+'\n')
parts.append(take('chapters/starter-chapter.tex',27,40))
parts.append(r'\end{center}'+'\n')
parts.append(r'''\captionof{figure}{Μετατόπιση κινητού από την αρχική θέση Α στην τελική θέση Β.}
\label{fig:displacement}\label{fig:starter-displacement}
''')
parts.append(take('chapters/demo-physics.tex',42,42))
parts.append(take('chapters/demo-physics.tex',43,53))
parts.append(r'''\captionof{figure}{Η θέση αυξάνεται γραμμικά με τον χρόνο.}
''')
parts.append(r'''Όπως φαίνεται στο Σχήμα~\ref{fig:displacement}, η μετατόπιση παριστάνεται με
διάνυσμα από την αρχική προς την τελική θέση.
''')
text='\n'.join(parts)
(OUT/'common-body.tex').write_text(text)
provenance.append({'editorial_additions':['Five topic headings and page breaks; counter/header initialization; no style/geometry/color redefinitions.','Supplementary page3 root/sum/nested-index/vector/Greek/Latin/chemical diagnostic formulas, explicitly labelled in visible Greek text. Roots and sums were not found in original demo/stress content. Integral, limits, fractions, kinematics, worked examples and diagrams reuse existing source.','Supplementary final ThinkBox on page4 explicitly labelled as typography diagnostic; probes inline roots, fractions, sums and mixed Greek/Latin at the actual small callout size.','Diagram captions use existing text and mathematical relations from source; labels assigned locally to avoid unrelated references.']})
for row in provenance:
    if row.get('source')=='stress-content.tex' and row.get('lines')==[5,9]:
        row['transformation']='Comment-only lines omitted; macro-closing brace outside the selected paragraph removed. Visible text and math retained.'
provenance.append({'common_body_sha256':hashlib.sha256(text.encode()).hexdigest(),'topic_order':['Physics theory with inline math and equation tag','Two existing worked examples with display solutions','Actual dense math plus explicitly labelled supplementary operator/Greek/Latin/chemistry diagnostics','Unmodified callout structures with actual content plus labelled dense-inline diagnostic','Two actual stable diagrams with original geometry/math labels'],'explicit_topic_page_breaks':4,'typography_diagnostic_wrapping':'Legal \\allowbreak points after commas in Greek/Latin variable lists; no variables removed and no math sizes changed.'})
(OUT/'CONTENT_PROVENANCE.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
print('Created',OUT/'common-body.tex')
