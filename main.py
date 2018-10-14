"""Main file for boox annotation conversion."""
import sys
import os
import shutil
import argparse
import logging

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfArray
from helper import (
    create_highlight,
    add_annot,
)
from pdf_text_search import(
    PDFTextSearch,
    TextNotFoundException,
    MultipleInstancesException
)
from boox_annot_reader import read_annotations

_LOGGER = logging.getLogger()
AUTHOR = 'Tin Lai'

def convert(input_file, use_new_file=False, backup_file=True):
    """Convert a given file's annotations."""
    annotations = read_annotations(input_file)
    if annotations is None:
        _LOGGER.info("Skipping...")
        return None
    if backup_file:
        backup(input_file)
    annotations = sorted(annotations, key=lambda x: x.page)
    if use_new_file:
        output = 'result.' + os.path.basename(input_file)
    else:
        output = os.path.basename(input_file)
    output = os.path.join(os.path.dirname(input_file), output)

    trailer = PdfReader(input_file)
    fitz_pdf = PDFTextSearch(input_file)
    for i, page in enumerate(trailer.pages):

        if annotations and i == annotations[0].page:
            page_num = i+1
            count = 0
            while annotations and i == annotations[0].page:
                _annot = annotations.pop(0)
                text = _annot.text
                try:
                    points = fitz_pdf.getQuadpoints(i, text)
                except TextNotFoundException:
                    # use fall back to try again
                    _LOGGER.debug("Page %d: Using fall-back mechanism."
                                  "Might contains mistaken hls.", page_num)
                    points = fitz_pdf.fallback_get_quadpoints(i, text)
                except MultipleInstancesException:
                    _LOGGER.error("Page %d: The following text found multiple instances,\n\n"
                                  "  --> \"%s\" <--  \n\n"
                                  "(Token too short?), please re-highligh it manually.",
                                  page_num, text)
                    continue
                highlight = create_highlight(points,
                                             author=AUTHOR,
                                             contents=_annot.comment,
                                             color=(1, 1, 0.4))
                # check to see if this annotation exists already
                if fitz_pdf.annot_exists(page_num=i, annot=highlight):
                    _LOGGER.debug("Page %d: This annot already exists, skipping...", page_num)
                else:
                    add_annot(page, annot=highlight)
                    count += 1
            print(">> Page {} successfully converted: {}".format(page_num, count))

    PdfWriter(output, trailer=trailer).write()
    return output

def handle_args():
    """Handle arguments for argparse."""
    parser = argparse.ArgumentParser(
        description="Convert Boox neoreader highlights annotation to standard "
                    "pdf format.")
    parser.add_argument(
        "file",
        help="File or directory as input. If the given argument is a directory, "
             "all files within will be the action target. The default action "
             "(without -c or -r flag) is to perform the annotation conversion "
             "action. (default: current working directory)",
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
        "--clean-entire-dir",
        action='store_true',
        default=False,
        help="Cleans up the enitre directory so that any annotation directory or "
             "bak files will be deleted; hence, implies --clean."
        )
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
    parser.add_argument(
        '-v',
        "--verbose",
        action='store_true',
        default=False,
        help="Be verbose in the status of conversion progress.")

    args = vars(parser.parse_args())
    if args['clean_entire_dir']:
        args['clean'] = True
    if args['verbose']:
        _LOGGER.setLevel(logging.DEBUG)
    else:
        _LOGGER.setLevel(logging.ERROR)
    # logger to stdout
    channel = logging.StreamHandler(sys.stdout)
    channel.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    _LOGGER.addHandler(channel)
    return args

def backup(inpfn):
    """Create a bak file for the given input file."""
    backup_file = '{}.bak'.format(inpfn)
    if os.path.isfile(backup_file):
        _LOGGER.info('Found backup pdf. Using the bak as input instead.')
        shutil.copyfile(backup_file, inpfn)
    else:
        shutil.copyfile(inpfn, backup_file)


def clean_up(inpfn):
    """Clean up for the given input file."""
    backup_file = '{}.bak'.format(inpfn)
    if os.path.isfile(backup_file):
        os.remove(backup_file)
        _LOGGER.debug("Deleting %s", backup_file)

def restore(inpfn, end_with_bak=False):
    """Restore the given input file."""
    if end_with_bak:
        backup_file = inpfn
        inpfn = inpfn[0:inpfn.rfind('.')]
    else:
        backup_file = '{}.bak'.format(inpfn)
    if os.path.isfile(backup_file):
        os.rename(backup_file, inpfn)
    elif not end_with_bak:
        _LOGGER.info("Bak file for '%s' does not exists.", inpfn)

def convert_wrapper(inpfn, args):
    """A wrapper for the convert function, for converting multiple files at once."""
    outfn = convert(input_file=inpfn, use_new_file=args['new_file'],
                    backup_file=(not args['no_backup']))
    if outfn is None:
        return
    # open result file with foxitreader (to re-save the format as it helps to fixes stuff)
    # need abs path becuase using relative path does not seems to mess up saving path
    last_modified_time = os.path.getmtime(outfn)
    import subprocess
    with open(os.devnull, 'w') as file_null:
        _LOGGER.debug('Opening %s', outfn)
        subprocess.call(['foxitreader', outfn], close_fds=True,
                        stdout=file_null, stderr=subprocess.STDOUT)
    # Check if user had saved the file after opening foxitreader
    if os.path.getmtime(outfn) <= last_modified_time:
        _LOGGER.warning("Seems like you did not save the file after opening foxitreader? "
                        "Its best to allow it do works for us on fixing internal PDF structures.")

def main():
    """Entry point when this file is run."""
    args = handle_args()
    if args['clean'] == args['restore'] and args['clean']:
        _LOGGER.error("The flag -c and -r are mutually exclusive, cannot be both set!")
        sys.exit(1)
    inpfn = os.path.abspath(args['file'])

    # for clean up or restore
    if os.path.isdir(inpfn):
        for file in os.listdir(inpfn):
            # prefix the file name with its directory
            file = os.path.join(inpfn, file)
            if file.endswith(".bak") and args['restore']:
                restore(file, end_with_bak=True)
            elif file.endswith(".pdf"):
                if args['clean_entire_dir']:
                    annot_path = os.path.splitext(file)[0]
                    if os.path.isdir(annot_path):
                        _LOGGER.debug("Deleting annot dir %s", annot_path)
                        shutil.rmtree(annot_path)
                if args['clean']:
                    clean_up(file)
                elif not args['clean'] and not args['restore']:
                    # Main functionality
                    print('='*80)
                    print(' {}'.format(os.path.basename(file)))
                    print('-'*80)
                    convert_wrapper(file, args)
                    print('')
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
