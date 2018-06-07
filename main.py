# -*- coding: utf-8 -*-
import sys
import os

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfArray
from helper import createHighlight, addAnnot, PDFTextSearch, TextNotFoundException
from booxAnnoReader import readAnnotations

AUTHOR = 'Tin Yiu Lai'


def main(inpfn):
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
            highlight = createHighlight(points,
                                        author=AUTHOR,
                                        contents=annotations[0].comment,
                                        color=[1,1,0.4])
            addAnnot(page, annot=highlight)
            print('OK')
            annotations.pop(0)
    print('==========')

    PdfWriter(outfn, trailer=trailer).write()
    return outfn

if __name__ == '__main__':
    argv = sys.argv[1:]
    underneath = '-u' in argv
    if underneath:
        del argv[argv.index('-u')]
    inpfn = argv[0]
    outfn = main(inpfn)

    abs_outfn = os.path.abspath(outfn)
    # open result file with foxitreader (to re-save the format as it helps to fixes stuff)
    # need abs path becuase using relative path does not seems to triggle saving when exiting foxitreader
    last_modified_time = os.path.getmtime(abs_outfn)
    import subprocess
    with open(os.devnull, 'w') as FNULL:
        subprocess.call(['foxitreader', abs_outfn], close_fds=True, stdout=FNULL, stderr=subprocess.STDOUT)
    # Check if user had saved the file after opening foxitreader
    if os.path.getmtime(abs_outfn) <= last_modified_time:
        print("WARNING! Seems like you did not save the file after opening foxitreader? "
              "Its best to allow it do works for us on fixing internal PDF structures.")
        sys.exit(1)
