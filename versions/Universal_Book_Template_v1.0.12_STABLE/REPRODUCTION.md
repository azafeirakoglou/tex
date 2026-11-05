# Αναπαραγωγή Universal Book Template v1.0.12

Όλες οι εντολές εκτελούνται από τη ρίζα ολόκληρου του πακέτου,
όπου βρίσκονται το `build_stable.py`, το `source/` και το `runtime/`.
Χρησιμοποιούμε νέο φάκελο, χωρίς αντικατάσταση προηγούμενης stable.

## Απαιτήσεις

Linux, Python 3.12, XeLaTeX/TeX Live, latexmk, fontconfig και DejaVu Sans/Mono.
Για τον τεχνικό έλεγχο χρειάζονται Ghostscript και Poppler
(`pdffonts`, `pdfinfo`, `pdftoppm`) και οι Python βιβλιοθήκες του
`requirements-review.txt`. Η απλή μεταγλώττιση χρησιμοποιεί μόνο
τη standard library της Python.

Η βάση δοκιμής είναι XeTeX 0.999996 (TeX Live 2025/dev/Debian),
latexmk 4.86 και Ghostscript 10.05.1. Οι ακριβείς εκδόσεις του τελικού
περιβάλλοντος καταγράφονται στην τεχνική αναφορά. Διαφορετικό TeX Live
μπορεί να αλλάξει στοιχειοθεσία ή αλλαγές σελίδων.

Ενδεικτικά Debian/Ubuntu packages: `texlive-xetex`, `texlive-latex-extra`,
`texlive-lang-greek`, `latexmk`, `fonts-dejavu-core`, `fontconfig`,
`ghostscript`, `poppler-utils`, `python3-venv`. Το setup του πακέτου δεν
εγκαθιστά ούτε αλλάζει εργαλεία συστήματος.

## Παραγωγή πλήρους PRINT και SCREEN

```sh
python3 prepare_runtime.py
python3 build_stable.py --jobs 2
```

Το πρώτο βήμα επαληθεύει τις συμπεριλαμβανόμενες γραμματοσειρές Inter,
Noto Serif και STIX Two Math, άδειες και ελληνικά πρότυπα συλλαβισμού
με SHA-256 από το `runtime/RUNTIME_MANIFEST.json`. Δημιουργεί τοπικό
format XeLaTeX και fontconfig, χωρίς download ή credentials.
Οι αρχικές πηγές εξαρτήσεων βρίσκονται στο
`source/scripts/dependency-manifest.json`. Τα TeX Live packages
χρησιμοποιούνται από την ήδη εγκατεστημένη διανομή συστήματος.

Το δεύτερο βήμα παράγει:

- `pdf/Universal_Book_Template_v1.0.12_PRINT.pdf`
- `pdf/Universal_Book_Template_v1.0.12_SCREEN.pdf`

Το περιεχόμενο παραμένει κοινό. Η προεπιλεγμένη κεφαλίδα παραδείγματος
είναι A στο `config/stable-config.tex`, με την τελική επιβεβαίωση επιλογής
στο `VERSION.json` / `QA_REPORT.md`. Για το starter:

```sh
python3 build_stable.py --targets starter-screen starter-print2
```

Οι φάκελοι `source/.local/`, `source/build/`, `runtime/texmf-var/`,
`runtime/cache/` και `runtime/tmp/` είναι αναδημιουργούμενοι.
Δεν απαιτείται ο αρχικός φάκελος `/workspace`, η v1.0.11 ή οποιαδήποτε
παλιά stable. Όλες οι νέες εγγραφές γίνονται μέσα στο αποσυμπιεσμένο
πακέτο. Μετά από μετακίνηση φακέλου ή αλλαγή TeX Live εκτελούμε ξανά
το `prepare_runtime.py`. Οι σχετικοί σύνδεσμοι runtime και το fontconfig
επαναδημιουργούνται από τον driver.

## Εναλλακτική κεφαλίδα παραδείγματος B

Μετά από το `config/book-config.tex` και πριν από την έναρξη περιεχομένου:

```tex
\renewcommand{\BookExampleHeaderVariant}{B}
```

Δεν αλλάζουμε το `BookEditorialMinimaltrue`. Οι A/B αφορούν μόνο κεφαλίδα
παραδείγματος και οι δύο δεν έχουν βούλα. Για σύγκριση ίδιων δειγμάτων:

```sh
python3 qa/probes/run_examples.py
python3 qa/probes/check_examples.py
python3 qa/probes/validate_examples.py
python3 tools/create_example_comparison.py
```

Τα τέσσερα A/B PRINT/SCREEN δοκίμια χρησιμοποιούν ακριβώς το ίδιο
`qa/probes/examples-content.tex`. Το συγκριτικό είναι
`pdf/EXAMPLE_HEADER_COMPARISON.pdf`, σελίδες πραγματικού μεγέθους 1:1.
Οι σελιδοδείκτες αναγνωρίζουν variant/profile. Εκτυπώνουμε στο 100%,
χωρίς Fit to page. Το συγκριτικό δεν είναι αρχείο παράδοσης τυπογραφείου.

## Πλήρης τεχνική επανάληψη

Αν χρειάζεται νέο τοπικό venv για τους ελέγχους:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-review.txt
```

Οι παρακάτω εντολές αναγεννούν τα fixtures και τα επιμέρους τεκμήρια:

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
python3 source/scripts/validate_pdf.py \
  --print qa/callouts/PRINT/callout-proof-print.pdf \
  --screen qa/callouts/SCREEN/callout-proof-screen.pdf \
  --map source/config/color-map.json --report qa/callouts/PREFLIGHT.json
python3 qa/tables/run_table_probe.py
python3 qa/tables/check_tail_boundary.py
python3 qa/create_summary.py
```

Η πλήρης σουίτα source tests και η τελική συγκεντρωτική αναφορά
περιγράφονται στο `QA_REPORT.md`, με τις εντολές και τα αποτελέσματα
της πραγματικής τελικής παραγωγής. Οι runners κάνουν νέα A/B QA αντίγραφα
στο `qa/work/` ώστε η δοκιμή B να μην αλλάζει την προεπιλεγμένη πηγή A.
Οι αναφορές με αρχικές απόλυτες διαδρομές είναι ιστορική προέλευση,
όχι απαίτηση ύπαρξης του αρχικού περιβάλλοντος. Αναγεννώνται από τους drivers.

Οι `tools/audit_integrity.py` και `reports/SOURCE_BASELINE.json` αφορούν
την προστασία του αρχικού workspace όπου δημιουργήθηκε η έκδοση.
Το integrity audit χρειάζεται εκείνα τα παλαιά αρχεία και δεν απαιτείται
στον υπολογιστή ενός νέου συγγραφέα. Τα αποτελέσματα περιλαμβάνονται ως
τεκμήριο· η παραγωγή του νέου βιβλίου παραμένει ανεξάρτητη.

Το `tools/clean_install_smoke.py` εκτελεί εγκατάσταση χωρίς `.local`,
build, format ή caches, με μετακίνηση του προετοιμασμένου φακέλου,
και συγκρίνει ολόκληρα τα νέα κύρια PDF με τα παραδοθέντα ως προς
κείμενο, θέσεις, διαστάσεις και rendering. Οι χρονικές σφραγίδες και
τα PDF IDs δεν απαιτείται να είναι byte-identical.

## Τοπική εγκατάσταση νέας έκδοσης και ZIP

Η συσκευασία δεν αλλάζει την κατάσταση του `VERSION.json`. Επιτρέπεται
μόνο μετά την ολοκλήρωση της αναφοράς QA και την καταγραφή `status: stable`.
Απαιτεί πρόσφατα, επιτυχή manifests και smoke test που αντιστοιχούν
στις πηγές και στα κύρια PDF. Για δημιουργία νέου φακέλου έκδοσης:

```sh
python3 tools/package_stable.py --install /διαδρομή/repository/versions/Universal_Book_Template_v1.0.12_STABLE
```

Η εντολή αρνείται να αντικαταστήσει υπάρχοντα φάκελο. Από τον νέο φάκελο
το `python3 tools/package_stable.py` δημιουργεί το ομώνυμο ZIP δίπλα του,
με CRC και SHA-256 για κάθε αρχείο. Το `--list` επιθεωρεί την επιλογή
αρχείων χωρίς εγκατάσταση ή ZIP. Δεν συμπεριλαμβάνονται προσωρινά
QA αντίγραφα, διαγνωστικές δοκιμές πινάκων, cache, aux ή compiled formats.

## Όρια

Το `VERSION.json` δηλώνει την κατάσταση του πακέτου και το `QA_REPORT.md`
τα αποτελέσματα. Ο χαρακτηρισμός stable αφορά τη μακέτα/ροή που ελέγχθηκε.
Δεν αποτελεί πιστοποίηση PDF/X ή τελική έγκριση φυσικού δοκιμίου.
Οι προδιαγραφές πραγματικού spot μελανιού και ξακρίσματος παραμένουν
στο `source/docs/PRESS_PENDING.md`.

Η προετοιμασία και η αναπαραγωγή δεν εκτελούν Git, push, merge ή release.
Απομακρυσμένη δημοσίευση απαιτεί τη χωριστή έγκριση που ζήτησε ο χρήστης.
