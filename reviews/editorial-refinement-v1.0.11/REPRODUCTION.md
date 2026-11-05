# Αναπαραγωγή του πακέτου αξιολόγησης v1.0.11

Το πακέτο περιέχει δύο ανεξάρτητες υποψήφιες μακέτες: A — REFINED και
B — MINIMAL. Δεν εκτελεί Git, push, merge ή release. Όλες οι παρακάτω εντολές
εκτελούνται από τη ρίζα του αποσυμπιεσμένου πακέτου σε νέο φάκελο.

## Απαιτήσεις συστήματος

Υποστηριζόμενη ροή: Linux, Python 3.12, TeX Live με XeLaTeX, latexmk,
fontconfig και DejaVu Sans/Mono. Για τον τεχνικό έλεγχο χρειάζονται επίσης
Ghostscript και Poppler (`pdffonts`, `pdfinfo`, `pdftoppm`).
Η βάση των δοκιμών είναι XeTeX 0.999996 (TeX Live 2025/dev/Debian),
latexmk 4.86 και Ghostscript 10.05.1. Διαφορετικό TeX Live μπορεί να αλλάξει
στοιχειοθεσία και αλλαγές σελίδων· οι γραμματοσειρές παραμένουν οι ίδιες.

Σε Debian/Ubuntu, αν λείπουν εργαλεία, ο διαχειριστής του υπολογιστή μπορεί
να εγκαταστήσει τα πακέτα `texlive-xetex`, `texlive-latex-extra`,
`texlive-lang-greek`, `latexmk`, `fonts-dejavu-core`, `fontconfig`,
`ghostscript`, `poppler-utils`, `python3-venv`. Το πακέτο αξιολόγησης
δεν εγκαθιστά ούτε μεταβάλλει εργαλεία συστήματος.

## Παραγωγή των τεσσάρων κύριων PDF

```sh
python3 prepare_runtime.py
python3 run_candidates.py --jobs 2
```

Το πρώτο βήμα επαληθεύει τα SHA-256 των ήδη συμπεριλαμβανόμενων
Inter, Noto Serif, STIX Two Math, αδειών και ελληνικών προτύπων συλλαβισμού.
Δημιουργεί τοπικό format XeLaTeX και τις ρυθμίσεις fontconfig. Δεν κατεβάζει
αρχεία και δεν απαιτεί credentials ή δίκτυο. Οι πηγές των αρχικών εξαρτήσεων
καταγράφονται επιπλέον στο `source/scripts/dependency-manifest.json`
κάθε πρότασης. Τα πρωτογενή TeX Live packages χρησιμοποιούνται από την
εγκατάσταση συστήματος και δεν περιλαμβάνονται στο ZIP.

Το δεύτερο βήμα παράγει μέσα στο `pdf/`:

- `v1.0.11_REFINED_PRINT.pdf`
- `v1.0.11_REFINED_SCREEN.pdf`
- `v1.0.11_MINIMAL_PRINT.pdf`
- `v1.0.11_MINIMAL_SCREEN.pdf`

Για μία μόνο πρόταση: `python3 run_candidates.py --designs MINIMAL`.
Οι δύο πλήρεις πηγαίοι κώδικες βρίσκονται στα `REFINED/source/` και
`MINIMAL/source/`. Δεν χρειάζεται ο αρχικός φάκελος stable ή το `working-base/`.
Η προετοιμασία και τα builds γράφουν μόνο μέσα στον αποσυμπιεσμένο φάκελο.
Οι συμβολικοί σύνδεσμοι `.local/`, το format, οι caches και τα `build/`
δημιουργούνται εκ νέου. Εκτελούμε ξανά το πρώτο βήμα μετά από μετακίνηση
του φακέλου ή αναβάθμιση TeX Live.

Τα PDF περιέχουν χρονικά μεταδεδομένα· σε νέα παραγωγή δεν απαιτείται
ταυτόσημο binary SHA-256. Τα κείμενα, οι θέσεις, οι σελίδες, οι γραμματοσειρές
και οι διαχωρισμοί ελέγχονται στα παρακάτω βήματα.

## Προαιρετική πλήρης επανάληψη των ελέγχων

Οι βιβλιοθήκες Python είναι απαραίτητες για τους ελέγχους και τη σύγκριση,
όχι για την απλή μεταγλώττιση. Χρησιμοποιούμε διαθέσιμο περιβάλλον Python
με τις εκδόσεις του `requirements-review.txt`, ή νέο τοπικό venv:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-review.txt
python qa/check_color_invariance.py
python tools/preflight_main.py
python qa/compat/run_compat.py
python qa/compat/validate_compat.py
python qa/suites/run_unit_suites.py
python qa/probes/run_editorial_probes.py
python qa/probes/validate_probe_pairs.py
python qa/compat/audit_build_logs.py
python qa/check_main_flow.py
python qa/create_summary.py
python proofs/openings/run_opening_probe.py
python proofs/openings/refresh_opening_evidence.py --extra-only
python proofs/openings/refresh_opening_evidence.py
python tools/create_comparison.py
```

Οι έλεγχοι μονάδων είναι 66 ανά πρόταση. Οι έλεγχοι συμβατότητας χτίζουν
40 πρόσθετα δείγματα και ελέγχουν 20 ζεύγη PRINT/SCREEN. Τα editorial probes
ελέγχουν πραγματικά μεγέθη γραμματοσειρών, σύνθετα μαθηματικά,
πολυγραμμικές λεζάντες, πολυσέλιδους πίνακες και μεγάλα διδακτικά κουτιά.
Τα reports του αρχικού πακέτου είναι αποδεικτικά της συγκεκριμένης παραγωγής:
ορισμένα περιέχουν τις αρχικές απόλυτες διαδρομές. Οι παραπάνω runners
αναγεννούν τις σχετικές αναφορές στο νέο περιβάλλον.

Το συγκριτικό PDF αντιγράφει όλες τις κύριες σελίδες σε κλίμακα 1:1,
170 × 240 mm, εναλλάξ A/B για SCREEN και μετά PRINT. Δεν προσθέτει
γραφικά ή χρώματα στις σελίδες. Bookmarks και page labels αναγνωρίζουν
την κάθε πρόταση. Ο έλεγχος `reports/COMPARISON_INTEGRITY.json`
επιβεβαιώνει τις διαστάσεις και την αντιστοιχία όλων των rendered σελίδων.
Δεν χρησιμοποιούμε το συγκριτικό ως αρχείο τυπογραφείου.

## Όρια της αξιολόγησης

Οι προτάσεις παραμένουν υπό επιλογή. Δεν εκτελούμε τους κληρονομημένους
μηχανισμούς release/export σε αυτή τη ροή. Το `ADOPTION_GUIDE.md`
περιγράφει τη μελλοντική υιοθέτηση μόνο μετά από έγκριση.
Απαιτείται νέο rendering και οπτική επιθεώρηση μετά από πραγματικές αλλαγές
περιεχομένου. Οι προδιαγραφές του τυπογραφείου για πραγματικό spot μελάνι,
ξάκρισμα και πρότυπο παράδοσης παραμένουν εκκρεμείς.
