# Έλεγχοι συγκριτικών PDF

Συνολική κατάσταση: **passed**.

| Εκδοχή | Σελίδες SCREEN/PRINT | Μαθηματικά inline/display (pt) | Αριθμός εξίσωσης (pt) | Έλεγχος μελανιών |
|---|---|---|---|---|
| A_CURRENT | 5/5 | 10.95001/10.95001 | 10.95001 | passed |
| B_STIX105 | 5/5 | 11.49756/11.49756 | 10.95001 | passed |
| C_STIX108 | 5/5 | 11.82598/11.82598 | 10.95001 | passed |
| D_STIX_FAMILY | 5/5 | 10.95001/10.95001 | 10.95001 | passed |
| E_LIBERTINUS | 5/5 | 10.95001/10.95001 | 10.95001 | passed |

## Παρατηρήσεις

- A_CURRENT: {"SCREEN": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 0, "benign_duplicate_spot_resource_warnings": 0, "unclassified_driver_warnings": 0}, "PRINT": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 0, "benign_duplicate_spot_resource_warnings": 0, "unclassified_driver_warnings": 0}}
  - SCREEN: Page 1: 5 span-bbox margin candidates; review actual ink
  - SCREEN: Page 3: 2 span-bbox margin candidates; review actual ink
  - SCREEN: Page 4: 1 span-bbox margin candidates; review actual ink
  - SCREEN: Page 5: 1 span-bbox margin candidates; review actual ink
  - PRINT: Page 1: 5 span-bbox margin candidates; review actual ink
  - PRINT: Page 3: 2 span-bbox margin candidates; review actual ink
  - PRINT: Page 4: 1 span-bbox margin candidates; review actual ink
  - PRINT: Page 5: 1 span-bbox margin candidates; review actual ink
- B_STIX105: {"SCREEN": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 0, "benign_duplicate_spot_resource_warnings": 0, "unclassified_driver_warnings": 0}, "PRINT": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 4, "benign_duplicate_spot_resource_warnings": 4, "unclassified_driver_warnings": 0}}
  - SCREEN: Page 1: 5 span-bbox margin candidates; review actual ink
  - SCREEN: Page 3: 1 span-bbox margin candidates; review actual ink
  - SCREEN: Page 4: 1 span-bbox margin candidates; review actual ink
  - SCREEN: Page 5: 1 span-bbox margin candidates; review actual ink
  - PRINT: Page 1: 5 span-bbox margin candidates; review actual ink
  - PRINT: Page 3: 1 span-bbox margin candidates; review actual ink
  - PRINT: Page 4: 1 span-bbox margin candidates; review actual ink
  - PRINT: Page 5: 1 span-bbox margin candidates; review actual ink
- C_STIX108: {"SCREEN": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 0, "benign_duplicate_spot_resource_warnings": 0, "unclassified_driver_warnings": 0}, "PRINT": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 4, "benign_duplicate_spot_resource_warnings": 4, "unclassified_driver_warnings": 0}}
  - SCREEN: Page 1: 5 span-bbox margin candidates; review actual ink
  - SCREEN: Page 3: 1 span-bbox margin candidates; review actual ink
  - SCREEN: Page 4: 1 span-bbox margin candidates; review actual ink
  - SCREEN: Page 5: 1 span-bbox margin candidates; review actual ink
  - PRINT: Page 1: 5 span-bbox margin candidates; review actual ink
  - PRINT: Page 3: 1 span-bbox margin candidates; review actual ink
  - PRINT: Page 4: 1 span-bbox margin candidates; review actual ink
  - PRINT: Page 5: 1 span-bbox margin candidates; review actual ink
- D_STIX_FAMILY: {"SCREEN": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 0, "benign_duplicate_spot_resource_warnings": 0, "unclassified_driver_warnings": 0}, "PRINT": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 4, "benign_duplicate_spot_resource_warnings": 4, "unclassified_driver_warnings": 0}}
- E_LIBERTINUS: {"SCREEN": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 0, "benign_duplicate_spot_resource_warnings": 0, "unclassified_driver_warnings": 0}, "PRINT": {"overfull": 0, "underfull": 0, "missing_glyph": 0, "font_warning": 0, "other_latex_warning": 4, "error": 0, "driver_warnings": 4, "benign_duplicate_spot_resource_warnings": 4, "unclassified_driver_warnings": 0}}

Οι μετρήσεις είναι σε TeX pt. Το πλήρες JSON διατηρεί PDF bp και τις πραγματικές θέσεις.
Η εκτύπωση στο 100% παραμένει η κατάλληλη τελική οπτική σύγκριση.

## Συμπληρωματικός έλεγχος συγκριτικού και οπτικής προεξοχής

Το `TYPOGRAPHY_COMPARISON.pdf` έχει 25 σελίδες 170 × 240 mm και όλες τις γραμματοσειρές ενσωματωμένες. Η αναφορά `COMPARISON_AND_PROTRUSION.json` καταγράφει το hash του και τα αποτελέσματα.

Στα A/B/C οι υποψήφιες υπερβάσεις του δεξιού ορίου είναι τελικές παύλες συλλαβισμού ή τελείες. Η προεξοχή του πραγματικού μελανιού φτάνει περίπου 0,6144 mm· το font advance box φτάνει 0,8851 mm. Τα ίδια δύο αποσπάσματα στην αρχική stable v1.0.10 έχουν ακριβώς τα ίδια πλάτη (απόκλιση κάτω από 0,000035 PDF bp). Πρόκειται για την προϋπάρχουσα οπτική προεξοχή της μικροτυπογραφίας, όχι για νέα αλλαγή γεωμετρίας ή overfull box. Δεν ισχυριζόμαστε ότι κάθε ίχνος μελανιού μένει αυστηρά μέσα στο ονομαστικό ορθογώνιο κειμένου.

Με κανονικοποίηση του γνωστού Inter mapping U+2206 → U+0394, το εξαγόμενο αλφαριθμητικό περιεχόμενο είναι ίδιο σε όλες τις παραλλαγές και τα δύο προφίλ. Τα αρχικά PDFs εμφάνιζαν δύο διαφορές εξαγωγής σε λέξεις που αρχίζουν με Δ· η κοινή πηγή TeX και τα ορατά γράμματα είναι ίδια.

## Προειδοποιήσεις που διατηρούνται

Κάθε βασικό PDF έχει τέσσερις κοινές προειδοποιήσεις `caption`: `captionof` εκτός box, αγνόηση `hypcap=true` για τις δύο λεζάντες και αχρησιμοποίητο `captionsetup[table]`. Το συγκριτικό περιεχόμενο αποφεύγει floats και δεν έχει πίνακα. Οι προειδοποιήσεις καταγράφονται ρητά και δεν είναι διαφορά ή αποτυχία συγκεκριμένης γραμματοσειράς. Οι τελικές μεταγλωττίσεις έχουν μηδέν overfull, underfull, missing-character, font-warning και TeX-error ευρήματα.

## Τοπική αύξηση διάστιχου σε inline κλάσμα

Το συνηθισμένο διάστιχο παραγράφων παραμένει περίπου 14,96 pt. Στην πρώτη σελίδα, όμως, η γραμμή με το inline κλάσμα `|Δx|/Δt` απαιτεί τοπικά μεγαλύτερη απόσταση από την προηγούμενη γραμμή: A **14,95989 pt**, B **16,20655 pt**, C **16,57794 pt**. Η επόμενη απόσταση επιστρέφει στα 14,96 pt. Η κλιμάκωση 105% συνεπώς δεν είναι απολύτως αόρατη στη ροή των γραμμών: το συγκεκριμένο διάστημα αυξάνεται κατά περίπου 1,247 pt, έναντι 1,618 pt στο 108%. Δεν εντοπίστηκε σύγκρουση πραγματικών περιγραμμάτων ή overfull box.
