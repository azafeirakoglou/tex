# Πειραματική τυπογραφική σύγκριση — v1.0.10

Η stable μακέτα **δεν τροποποιήθηκε**. Ο κατάλογος περιέχει ανεξάρτητη αξιολόγηση πέντε επιλογών, ολοκληρωμένη στις 05/11/2026.

## Ξεκίνα από εδώ

1. Άνοιξε το [TYPOGRAPHY_COMPARISON.pdf](TYPOGRAPHY_COMPARISON.pdf): 25 σελίδες, όλες 17 × 24 cm, με πέντε θεματικές ομάδες. Σε κάθε ομάδα εμφανίζονται διαδοχικά A, B, C, D, E.
2. Διάβασε τη σύσταση και τα όρια στο [TYPOGRAPHY_REVIEW.md](TYPOGRAPHY_REVIEW.md).
3. Οι προτεινόμενες μελλοντικές αλλαγές περιγράφονται στο [TYPOGRAPHY_IMPLEMENTATION.md](TYPOGRAPHY_IMPLEMENTATION.md). Δεν εφαρμόστηκαν στη stable.
4. Για χαρτί επίλεξε **Πραγματικό μέγεθος / 100%**, χωρίς Fit ή Shrink. Τα PRINT χρησιμοποιούν το υπάρχον προσωρινό κόκκινο spot της μακέτας.

Η πρώτη πρόταση είναι **B — STIX 105%**: επαρκής μικρή βελτίωση, με καταγεγραμμένη τοπική αύξηση διάστιχου περίπου 1,25 pt σε γραμμή με inline κλάσμα. Η C — 108% παραμένει λειτουργική. Οι D/E είναι διαφορετικές οικογενειακές εκδοτικές κατευθύνσεις.

## Τα δέκα PDF

Κάθε αρχείο έχει πέντε ίδιες θεματικές σελίδες: θεωρία, λυμένα παραδείγματα, πυκνά μαθηματικά/χημική γραφή, διδακτικά κουτιά, διαγράμματα.

| Εκδοχή | SCREEN | PRINT |
|---|---|---|
| A — Current | [A_CURRENT_SCREEN.pdf](pdf/A_CURRENT_SCREEN.pdf) | [A_CURRENT_PRINT.pdf](pdf/A_CURRENT_PRINT.pdf) |
| B — STIX 105% | [B_STIX105_SCREEN.pdf](pdf/B_STIX105_SCREEN.pdf) | [B_STIX105_PRINT.pdf](pdf/B_STIX105_PRINT.pdf) |
| C — STIX 108% | [C_STIX108_SCREEN.pdf](pdf/C_STIX108_SCREEN.pdf) | [C_STIX108_PRINT.pdf](pdf/C_STIX108_PRINT.pdf) |
| D — Πλήρης STIX | [D_STIX_FAMILY_SCREEN.pdf](pdf/D_STIX_FAMILY_SCREEN.pdf) | [D_STIX_FAMILY_PRINT.pdf](pdf/D_STIX_FAMILY_PRINT.pdf) |
| E — Libertinus | [E_LIBERTINUS_SCREEN.pdf](pdf/E_LIBERTINUS_SCREEN.pdf) | [E_LIBERTINUS_PRINT.pdf](pdf/E_LIBERTINUS_PRINT.pdf) |

## Περιεχόμενα και αποδεικτικά

- `content/`: κοινό TeX, generator και ακριβής προέλευση αποσπασμάτων.
- `source/`: ανέπαφο αντίγραφο των πηγών v1.0.10· δεν περιέχει Git repository.
- `variants/`: ανεξάρτητα entrypoints και τυπογραφικά overrides.
- `runtime/fonts/`: οι αρχικές, κλειδωμένες γραμματοσειρές.
- `runtime/texmf/`: τοπικά ελληνικά patterns και δήλωση γλώσσας.
- `fonts/installed/`, `fonts/licenses/`: νέες πραγματικές γραμματοσειρές και άδειες όλων των οικογενειών.
- `fonts/FONT_MANIFEST.json`: URLs, commits, SHA-256, βάρη και ελληνική κάλυψη.
- `fonts/probes/`: πρόσθετα τεχνικά δοκίμια πολυτονικού. Αυτά είναι αποδεικτικά, όχι επιπλέον βασικές τυπογραφικές εκδοχές.
- `previews/`, `visual-audit/`: εικόνες κοινής κλίμακας για οπτική σύγκριση.
- `qa/`: μετρήσεις, πέντε έλεγχοι PRINT/SCREEN και έλεγχος πραγματικών περιγραμμάτων. Το `implementation-probe/` ελέγχει μόνο την προτεινόμενη σύνταξη, εκτός stable.
- `reports/`: αρχικές τιμές, εργαλεία και τεκμηρίωση σύγκρισης.
- `BASELINE_GIT_AND_FILES.json`, `STABLE_INTEGRITY.json`: αρχική και τελική προστασία της stable.
- `PACKAGE_CONTENTS.json`, `SHA256SUMS.txt`: κατάλογος και έλεγχοι ακεραιότητας πακέτου.

Τα μεγάλα αρχικά downloads γραμματοσειρών, τα δυαδικά format/cache και οι ενδιάμεσοι κατάλογοι `build/` δεν είναι αναγκαίοι για την ανάγνωση και εξαιρούνται από το ZIP.

## Αναπαραγωγή σε Linux / συμβατό περιβάλλον TeX

Η παραγωγή ελέγχθηκε με XeTeX/TeX Live 2025, latexmk 4.86, Ghostscript 10.05.1 και Python 3.12.14. Ακριβείς εκδόσεις Python βιβλιοθηκών υπάρχουν στα `requirements-review.txt` και `reports/TOOLCHAIN.json`. Χρειάζονται επίσης `fontconfig`, οι LaTeX εξαρτήσεις της μακέτας και τα εργαλεία `fmtutil-user`, `xelatex`, `latexmk`, `gs`. Οι πραγματικές γραμματοσειρές περιλαμβάνονται με τις άδειές τους· δεν χρειάζεται αδήλωτο fallback ή global εγκατάσταση.

Από τον κατάλογο του review:

```sh
mkdir -p runtime/tmp
python3 -m venv .venv
TMPDIR="$PWD/runtime/tmp" .venv/bin/python -m pip install --no-cache-dir -r requirements-review.txt
.venv/bin/python prepare_runtime.py
.venv/bin/python run_review.py --jobs 2
.venv/bin/python make_comparison.py
```

Το `prepare_runtime.py` ετοιμάζει fontconfig και ελληνικό format αποκλειστικά στο `runtime/`. Το format αναδημιουργείται με τον τοπικό XeTeX, ώστε να μη μεταφέρεται ασύμβατο δυαδικό format μεταξύ εγκαταστάσεων. Το βήμα προετοιμασίας δοκιμάστηκε στο ανεξάρτητο περιβάλλον. Οι παραπάνω εντολές γράφουν μόνο μέσα στο review. Ο generator αποσπασμάτων δεν χρειάζεται να εκτελεστεί: το τελικό κοινό `common-body.tex` περιλαμβάνεται ήδη.

Η αρχική καταγραφή και η επιβεβαίωση του Git αφορούν το αποθετήριο που ήταν διαθέσιμο κατά την αξιολόγηση· τα πειραματικά PDF παράγονται από το παρεχόμενο αντίγραφο πηγών. Δεν απαιτείται merge ή αλλαγή της εγκεκριμένης μακέτας.
