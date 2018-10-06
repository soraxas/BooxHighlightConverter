import sys
import os
import shutil
import argparse

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfArray
from helper import createHighlight, addAnnot, PDFTextSearch, TextNotFoundException
from booxAnnoReader import readAnnotations

AUTHOR = 'Tin Lai'


def convert(input_file, use_new_file=False, backup_file=True):
    annotations = readAnnotations(input_file)
    if annotations is None:
        print("Skipping '{}'...".format(input_file))
        return None
    if backup_file:
        backup(input_file)
    annotations = sorted(annotations, key=lambda x: x.page)
    if use_new_file:
        output = 'result.' + os.path.basename(input_file)
    else:
        output = os.path.basename(input_file)
    path_name = os.path.dirname(input_file)
    output = os.path.join(path_name, output)

    trailer = PdfReader(input_file)
    fitz_pdf = PDFTextSearch(input_file)
    for i, page in enumerate(trailer.pages):

        if annotations and i == annotations[0].page:
            print('=== Page {} ==='.format(i+1))
            count = 0
            while annotations and i == annotations[0].page:
                text = annotations[0].text
                try:
                    points = fitz_pdf.getQuadpoints(i, text)
                except TextNotFoundException:
                    # use fall back to try again
                    print("INFO: Using fall-back mechanism. Might contains mistaken hls.")
                    points = fitz_pdf.fallbackGetQuadpoints(i, text)
                highlight = createHighlight(points,
                                            author=AUTHOR,
                                            contents=annotations[0].comment,
                                            color=[1, 1, 0.4])
                # check to see if this annotation exists already
                if fitz_pdf.annot_exists(page_num=i, annot=highlight):
                    print("INFO: This annot already exists, skipping...")
                else:
                    addAnnot(page, annot=highlight)
                    count += 1
                annotations.pop(0)
            print(">> Successfully converted: {}".format(count))
    print('==========')

    PdfWriter(output, trailer=trailer).write()
    return output

def handle_args():
    parser = argparse.ArgumentParser(
        description="Convert Boox neoreader highlights annotation to standard \
                     pdf format.")
    parser.add_argument(
        "file",
        help="File or directory as input. If the given argument is a directory, \
              all files within will be the action target. The default action \
              (without -c or -r flag) is to perform the annotation conversion \
              action. (default: current working directory)",
        nargs='?',
        default=os.getcwd(),
        metavar="FILE_OR_DIR")
    parser.add_argument(
        "-c",
        "--clean",
        action='store_true',
        default=False,
        help="Cleans up the bak files from current directory.")
    parser.add_argument(
        "-r",
        "--restore",
        action='store_true',
        default=False,
        help="Use existing bak file to restore and overwrite the original pdf files.")
    parser.add_argument(
        "-n",
        "--new-file",
        action='store_true',
        default=False,
        help="Create a new file instead of overwriting the input file.")
    parser.add_argument(
        "--no-backup",
        action='store_true',
        default=False,
        help="Do not create a bak file (dangeous if using original file).")

    args = vars(parser.parse_args())
    return args

def backup(inpfn):
    backup_file = '{}.bak'.format(inpfn)
    if os.path.isfile(backup_file):
        print('INFO: Found backup pdf. Using the bak as input instead.')
        shutil.copyfile(backup_file, inpfn)
    else:
        shutil.copyfile(inpfn, backup_file)


def clean_up(inpfn):
    backup_file = '{}.bak'.format(inpfn)
    if os.path.isfile(backup_file):
        os.remove(backup_file)
        print("INFO: Deleting {}".format(backup_file))

def restore(inpfn, end_with_bak=False):
    if end_with_bak:
        backup_file = inpfn
        inpfn = inpfn[0:inpfn.rfind('.')]
    else:
        backup_file = '{}.bak'.format(inpfn)
    if os.path.isfile(backup_file):
        os.rename(backup_file, inpfn)
    elif not end_with_bak:
        print("WARN: Bak file for '{}' does not exists.".format(inpfn))

def convert_wrapper(inpfn, args):
    outfn = convert(input_file=inpfn, use_new_file=args['new_file'], backup_file=(not args['no_backup']))
    if outfn is None:
        return
    # open result file with foxitreader (to re-save the format as it helps to fixes stuff)
    # need abs path becuase using relative path does not seems to triggle saving when exiting foxitreader
    last_modified_time = os.path.getmtime(outfn)
    import subprocess
    with open(os.devnull, 'w') as FNULL:
        print('Opening {}'.format(outfn))
        subprocess.call(['foxitreader', outfn], close_fds=True, stdout=FNULL, stderr=subprocess.STDOUT)
    # Check if user had saved the file after opening foxitreader
    if os.path.getmtime(outfn) <= last_modified_time:
        print("WARNING! Seems like you did not save the file after opening foxitreader? "
              "Its best to allow it do works for us on fixing internal PDF structures.")

def main():
    args = handle_args()
    if args['clean'] == args['restore'] and args['clean'] == True:
        print("The flag -c and -r are mutually exclusive, annot be both set!")
        sys.exit(1)
    inpfn = os.path.abspath(args['file'])

    # for clean up or restore
    if os.path.isdir(inpfn):
        for file in os.listdir(inpfn):
            if file.endswith(".bak"):
                if args['restore']:
                        restore(file, end_with_bak=True)
            elif file.endswith(".pdf"):
                if args['clean']:
                    clean_up(file)
                elif not args['clean'] and not args['restore']:
                    # Main functionality
                    print('-'*40)
                    convert_wrapper(file, args)
    else:
        if args['clean']:
            clean_up(inpfn)
        elif args['restore']:
            restore(inpfn)
        else:
            # Main functionality
            convert_wrapper(inpfn, args)


if __name__ == '__main__':
    main()
