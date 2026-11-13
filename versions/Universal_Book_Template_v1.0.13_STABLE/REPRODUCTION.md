# Αναπαραγωγή Universal Book Template v1.0.13

Οι εντολές εκτελούνται από τη ρίζα ολόκληρου του πακέτου, όπου βρίσκονται
τα `build_stable.py`, `prepare_runtime.py`, `source/` και `runtime/`.
Αποσυμπιέζουμε σε νέο φάκελο, χωρίς αντικατάσταση προηγούμενης stable.

## Απαιτήσεις

Η δοκιμασμένη πλατφόρμα είναι Debian GNU/Linux 13, Python 3.12.14,
XeTeX 0.999996 (TeX Live 2025/dev/Debian), latexmk 4.86 και fontconfig.
Χρειάζονται τα εργαλεία `fc-cache`, `kpsewhich`, `fmtutil-user`, `xetex`,
`xelatex`, `latexmk` και οι DejaVu Sans/Mono του συστήματος.
Η απλή μεταγλώττιση χρησιμοποιεί μόνο τη standard library της Python.

Οι τεχνικοί έλεγχοι χρησιμοποιούν επίσης Ghostscript 10.05.1,
Poppler (`pdffonts`, `pdfinfo`, `pdftoppm`) και τις κλειδωμένες βιβλιοθήκες
του `requirements-review.txt`. Ενδεικτικά Debian/Ubuntu packages:
`texlive-xetex`, `texlive-latex-extra`, `texlive-lang-greek`, `latexmk`,
`fonts-dejavu-core`, `fontconfig`, `ghostscript`, `poppler-utils`,
`python3-venv`. Το setup του πακέτου δεν εγκαθιστά εργαλεία συστήματος.
Άλλη έκδοση TeX Live μπορεί να αλλάξει στοιχειοθεσία ή σελιδοποίηση.

## Πλήρη PRINT και SCREEN

```sh
python3 prepare_runtime.py
python3 build_stable.py --jobs 2
```

Το setup επαληθεύει με SHA-256 τις συμπεριλαμβανόμενες Inter, Noto Serif,
STIX Two Math, άδειες και ελληνικά πρότυπα συλλαβισμού, με βάση το
`runtime/RUNTIME_MANIFEST.json`. Δημιουργεί τοπικό format XeLaTeX και
fontconfig χωρίς download ή credentials. Τα TeX Live packages προέρχονται
από την εγκατεστημένη διανομή συστήματος. Το
`source/scripts/dependency-manifest.json` τεκμηριώνει την αρχική προέλευση
των εξαρτήσεων· δεν χρειάζεται επανάληψη των downloads του παλαιού setup.

Παράγονται:

- `pdf/Universal_Book_Template_v1.0.13_PRINT.pdf`
- `pdf/Universal_Book_Template_v1.0.13_SCREEN.pdf`
- `BUILD_RESULTS.json` και πλήρη logs στο `logs/`.

Οι δύο εκδόσεις μοιράζονται την ίδια ύλη. Η κεφαλίδα λυμένων παραδειγμάτων
A παραμένει προεπιλογή. Για το μικρό σημείο εκκίνησης νέου βιβλίου:

```sh
python3 build_stable.py --targets starter-screen starter-print2
```

Τα αποτελέσματα του starter βρίσκονται στο `source/build/starter-screen/`
και `source/build/starter-print2/`. Η χρήση και οι δημόσιες συντάξεις
περιγράφονται στο `source/docs/AUTHORING.md`.

Τα `source/.local/`, `source/build/`, `runtime/texmf-var/`,
`runtime/texmf-config/`, `runtime/cache/` και `runtime/tmp/` αναδημιουργούνται.
Η παραγωγή δεν απαιτεί τον αρχικό φάκελο εργασίας ή παλαιότερη stable.
Όλες οι εγγραφές παραγωγής γίνονται μέσα στο νέο πακέτο. Μετά από
μετακίνηση φακέλου ή αλλαγή TeX Live εκτελούμε ξανά `prepare_runtime.py`.
Οι σχετικοί σύνδεσμοι runtime παραμένουν μέσα στο πακέτο και το fontconfig
ενημερώνεται για τη νέα θέση από τον driver.

## Προαιρετική κεφαλίδα παραδείγματος B

Μετά το `config/book-config.tex` και πριν από το περιεχόμενο:

```tex
\renewcommand{\BookExampleHeaderVariant}{B}
```

Το `BookEditorialMinimaltrue` παραμένει ενεργό. Τα A/B αφορούν μόνο την
κεφαλίδα παραδείγματος. Οι δοκιμές B χρησιμοποιούν απομονωμένη πηγή στο
`qa/work/B/`, χωρίς μεταβολή της κανονικής προεπιλογής A.

## Επανάληψη τεχνικών ελέγχων

Αν λείπουν οι βιβλιοθήκες ελέγχου, προετοιμάζουμε περιβάλλον Python
πριν από την offline επανάληψη:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-review.txt
```

Μετά το setup/build, οι παρακάτω εντολές αναγεννούν τα τεχνικά δοκίμια
και τα αποτελέσματά τους:

```sh
python3 qa/driver.py
python3 qa/check_color_invariance.py
python3 qa/main/run_preflight.py
python3 qa/suites/run_unit_suite.py
python3 qa/compat/run_compat.py
python3 qa/compat/validate_compat.py
python3 qa/compat/audit_build_logs.py
python3 qa/probes/run_editorial_probes.py
python3 qa/probes/validate_probe_pairs.py
python3 qa/probes/run_examples.py
python3 qa/probes/check_examples.py
python3 qa/probes/validate_examples.py
python3 qa/callouts/run_callout_proof.py
python3 qa/callouts/check_callout_proof.py
python3 qa/callouts/run_preflight.py
python3 qa/tables/run_table_probe.py
python3 qa/tables/check_tail_boundary.py
python3 qa/refinement/run_refinement.py
python3 qa/material/run_material_probe.py
python3 qa/icons/run_icon_proof.py
python3 qa/icons/verify_icon_proof.py
python3 tools/clean_install_smoke.py
```

Η σουίτα περιλαμβάνει 66 tests, 40 builds συμβατότητας σε A/B και
8 ελεγχόμενα editorial probes. Τα επιμέρους reports δίνουν πραγματικό
πλήθος, διαγνωστικά και SHA-256. Οι runners εικονιδίων αναπαράγουν τις νέες
PRINT/SCREEN πηγές χωρίς παλιό workspace. Για τη σύγκριση ύψους διατηρείται
το τελικό baseline PDF στο `qa/icons/BASELINE_SCREEN/`. Η προαιρετική
`--baseline-source /διαδρομή/παλιάς/source` του `run_icon_proof.py`
αναγεννά αυτό το συγκριτικό από ιδιωτικό προσωρινό αντίγραφο· δεν αλλάζει
την παλιά πηγή και δεν αποτελεί προϋπόθεση του κανονικού build.

Το `tools/clean_install_smoke.py` δημιουργεί νέο ZIP εισόδου μόνο με πηγές
και κλειδωμένες εξαρτήσεις, το αποσυμπιέζει χωρίς `.local`, build, format ή
cache, προετοιμάζει το runtime και μετακινεί τον φάκελο πριν το πλήρες build.
Συγκρίνει και τις 40 σελίδες των κύριων PDF ως προς γεωμετρία, κείμενο,
θέσεις με ανοχή 0,02 bp και ακριβές rendering στα 72 dpi. Επαληθεύει το
πλήρες manifest πηγών πριν και μετά την παραγωγή. Τα PDF IDs και οι
χρονικές σφραγίδες δεν απαιτείται να είναι byte-identical.

Το `QA_REPORT.md` και τα `qa/QA_SUMMARY.json`,
`visual-audit/VISUAL_EVIDENCE.json` καταγράφουν την τελική τεχνική και
πραγματική οπτική κάλυψη. Οι μηχανικοί έλεγχοι δεν υποκαθιστούν θέαση
των πλήρων σελίδων, των αλλαγμένων πλαισίων και των μεγάλων τίτλων.
Μετά από αλλαγές ανανεώνουμε τους σχετικούς ελέγχους/οπτικά τεκμήρια και
εκτελούμε `python3 qa/create_summary.py`. Η εντολή δεν προάγει έκδοση.
Το τελικό συγκριτικό των τροποποιημένων περιοχών είναι
`pdf/REFINEMENT_PROOF.pdf`· το εκτυπώνουμε στο 100%, χωρίς Fit to page.

Τα `tools/audit_integrity.py`, `tools/source_diff.py` και
`reports/SOURCE_BASELINE.json` τεκμηριώνουν την ακεραιότητα του αρχικού
workspace και τη διαφορά από τη v1.0.12. Το integrity audit χρειάζεται
εκείνα τα προστατευμένα αρχεία και το αρχικό repository. Δεν απαιτούνται
στον υπολογιστή νέου συγγραφέα. Απόλυτες διαδρομές σε ιστορικά logs/reports
καταγράφουν προέλευση και δεν αποτελούν εξαρτήσεις της παραγωγής.

## Νέος φάκελος έκδοσης και ZIP

Το packaging δεν αλλάζει το `VERSION.json`. Πριν από εγκατάσταση/ZIP
απαιτούνται `status: stable`, ολοκληρωμένο QA v1.0.13, συγκριτικό proof,
επιτυχή integrity/source manifests και πρόσφατο smoke δεμένο στις τρέχουσες
πηγές και στα δύο κύρια PDF. Η επιλογή αρχείων ελέγχεται χωρίς εγγραφή:

```sh
python3 tools/package_stable.py --list
```

Για εγκατάσταση σε νέο φάκελο έκδοσης:

```sh
python3 tools/package_stable.py --install /διαδρομή/repository/versions/Universal_Book_Template_v1.0.13_STABLE
```

Η εγκατάσταση αρνείται να αντικαταστήσει υπάρχοντα φάκελο και ελέγχει
το SHA-256 κάθε αντιγράφου. Από τη ρίζα του νέου εγκατεστημένου φακέλου:

```sh
python3 tools/package_stable.py
python3 tools/clean_install_smoke.py --archive ../Universal_Book_Template_v1.0.13_STABLE.zip
```

Το ομώνυμο ZIP δημιουργείται δίπλα στον φάκελο stable, με CRC και manifest
`PACKAGE_CONTENTS.json` για κάθε αρχείο. Ο έλεγχος `--archive` ελέγχει το
πραγματικό παραδοτέο ZIP. Αν ενημερωθεί report μέσα στον φάκελο μετά το ZIP,
ξαναδημιουργούμε το ZIP ώστε το περιεχόμενο και τα hashes να συμφωνούν.
Περιλαμβάνονται τα τελικά component proofs/reports. Αποκλείονται `.local`,
builds, caches, aux, compiled formats, `qa/work/`, `qa/main-preview/`,
αντίγραφα baseline πηγών, candidates και διαγνωστικές δοκιμές.

Τα setup/build/package helpers δεν εκτελούν Git. Το brief εγκρίνει commit
`Release Universal Book Template v1.0.13 STABLE` και κανονικό push στον
ήδη ρυθμισμένο κλάδο μετά τους επιτυχείς ελέγχους. Δεν επιτρέπονται
force push, merge σε άλλον κλάδο ή αντικατάσταση προηγούμενης stable.
Το τελικό branch, hash και αποτέλεσμα push αναφέρονται χωριστά.

Ο χαρακτηρισμός stable αφορά την ελεγμένη μακέτα και την αναπαραγώγιμη
ροή. Οι τελικές προδιαγραφές πραγματικού spot, ξακρίσματος και φυσικού
δοκιμίου παραμένουν στο `source/docs/PRESS_PENDING.md`.
