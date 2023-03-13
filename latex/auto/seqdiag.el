(TeX-add-style-hook
 "seqdiag"
 (lambda ()
   (TeX-add-to-alist 'LaTeX-provided-class-options
                     '(("standalone" "margin=2mm")))
   (TeX-run-style-hooks
    "latex2e"
    "standalone"
    "standalone10"
    "pgf-umlsd")
   (TeX-add-symbols
    "hnd"))
 :latex)

