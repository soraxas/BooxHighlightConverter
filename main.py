import sys
import os

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfArray
from helper import createHighlight, addAnnot, PDFTextSearch, TextNotFoundException
from booxAnnoReader import readAnnotations

AUTHOR = 'Tin Yiu Lai'


def main(inpfn, use_new_file=False):
    annotations = readAnnotations(inpfn)
    annotations = sorted(annotations, key=lambda x: x.page)
    if use_new_file:
        outfn = 'result.' + os.path.basename(inpfn)
    else:
        outfn = os.path.basename(inpfn)
    path_name = os.path.dirname(inpfn)
    outfn = os.path.join(path_name, outfn)

    trailer = PdfReader(inpfn)
    fitz_pdf = PDFTextSearch(inpfn)
    for i, page in enumerate(trailer.pages):
        print('==  Page {:>3}  =='.format(i))

        while annotations and i == annotations[0].page:
            text = annotations[0].text
            try:
                points = fitz_pdf.getQuadpoints(i, text)
            except TextNotFoundException as e:
                # use fall back to try again
                print("> Using fall-back mechanism at page '{}'. Might not be fully correct".format(i+1))
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

def backup_ori(inpfn):
    from shutil import copyfile
    backup_file = '{}.bak'.format(inpfn)
    if os.path.isfile(backup_file):
        print('INFO: Found backup pdf. Using the bak as input instead.')
        copyfile(backup_file, inpfn)
    else:
        copyfile(inpfn, backup_file)

if __name__ == '__main__':
    argv = sys.argv[1:]
    if len(argv) < 1:
        print("You need to supply a pdf filename for highlight annotations conversion.")
        print("Optionally use --use-new-file or -n to save result in a separate file.")
        sys.exit(1)
    use_new_file = '--use-new-file' in argv or '-n' in  argv
    inpfn = argv[0]
    inpfn = os.path.abspath(inpfn)
    # backup original file
    backup_ori(inpfn)
    outfn = main(inpfn, use_new_file)
    # open result file with foxitreader (to re-save the format as it helps to fixes stuff)
    # need abs path becuase using relative path does not seems to triggle saving when exiting foxitreader
    last_modified_time = os.path.getmtime(outfn)
    import subprocess
    with open(os.devnull, 'w') as FNULL:
        print('Opeining {}'.format(outfn))
        subprocess.call(['foxitreader', outfn], close_fds=True, stdout=FNULL, stderr=subprocess.STDOUT)
    # Check if user had saved the file after opening foxitreader
    if os.path.getmtime(outfn) <= last_modified_time:
        print("WARNING! Seems like you did not save the file after opening foxitreader? "
              "Its best to allow it do works for us on fixing internal PDF structures.")
        sys.exit(1)
