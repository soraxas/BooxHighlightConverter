# -*- coding: utf-8 -*-
import sys
import os

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfArray
from helper import createHighlight, addAnnot, PDFTextSearch, TextNotFoundException
from booxAnnoReader import readAnnotations

AUTHOR = 'Tin Yiu Lai'

argv = sys.argv[1:]
underneath = '-u' in argv
if underneath:
    del argv[argv.index('-u')]

inpfn = argv[0]

annotations = readAnnotations(inpfn)
annotations = sorted(annotations, key=lambda x: x.page)


outfn = 'result.' + os.path.basename(inpfn)
# wmark = PageMerge().add(PdfReader(wmarkfn).pages[0])[0]
trailer = PdfReader(inpfn)
fitz_pdf = PDFTextSearch(inpfn)
for i, page in enumerate(trailer.pages):
    print('==========')
    print(i)

    while annotations and i == annotations[0].page:
        text = annotations[0].text
        try:
            points = fitz_pdf.getQuadpoints(i, text)
        except TextNotFoundException as e:
            # use fall back to try again
            print("> Using fall-back mechanism at page '{}'. Might not be fully correct".format(i))
            points = fitz_pdf.fallbackGetQuadpoints(i, text)
        highlight = createHighlight(points, author=AUTHOR, contents=annotations[0].comment)
        addAnnot(page, annot=highlight)
        print('OK')
        annotations.pop(0)


        # addAnnot(page, annot=highlight)
        # print(page.Annots)


    # PageMerge(page).add(wmark, prepend=underneath).render()
PdfWriter(outfn, trailer=trailer).write()
