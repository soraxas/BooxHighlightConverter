"""
For conveting annotation from a boox annotated file.
"""
import os
import re
import logging

_LOGGER = logging.getLogger()

class Annot:
    """Class that represents an annotation."""
    def __init__(self):
        self.page = None
        self.text = ""
        self.comment = None

def read_annotations(pdf_path):
    """Read annotations from folder that hold the .txt file, then return the text."""
    path_name = os.path.splitext(pdf_path)[0]
    base_name_with_ext = os.path.basename(pdf_path)
    base_name = os.path.splitext(base_name_with_ext)[0]
    annotation_file_name = os.path.join(path_name, base_name + '-annotation.txt')
    if not os.path.isfile(annotation_file_name):
        _LOGGER.debug("Expected annotation file does not exists.")
        return None
    annot_file = open(annotation_file_name)
    begining_anno = True
    ended = False
    annotations = []
    for line in annot_file.readlines():
        ##############################
        ##  REPLACE INVALID TOKENS  ##
        ##############################
        # this indicate some token that the program cannot recognise (as place holder)
        if "\xef\xbf\xbe" in line:
            # It likely to be a hyphen for word break. Replace it as '-'.
            line = line.replace("\xef\xbf\xbe", '-\n')
        ###########################
        if begining_anno:
            ### Page line + Comment
            annotations.append(Annot())

            begining_anno = False
            match_obj = re.match(r'(?:Page )([0-9]+)\s{1,2}(.*)?\n', line)

            if not match_obj:
                raise Exception("Error in parsing first line")

            annotations[-1].page = match_obj.group(1)
            annotations[-1].comment = match_obj.group(2)
        elif '\x00' in line:
            ### Last line before End of annotation
            ended = True
            line = line.replace('\x00', '')
            annotations[-1].text += line
        elif '--------------------' in line:
            ### End of annotation
            if not ended:
                raise Exception("Did not detect \\x00 indicating end of line?")
            begining_anno = True
            ended = False
            # fix ups the formatting of each components
            # NOTE this -1 because in the program index starts at 0
            annotations[-1].page = int(annotations[-1].page) - 1
            annotations[-1].text = annotations[-1].text.rstrip()
            annotations[-1].comment = annotations[-1].comment.rstrip()
            if not annotations[-1].comment:
                # remove empty comment
                annotations[-1].comment = None
        elif '\r\n' in line:
            ### text (highlighted pdf text)
            annotations[-1].text += line
        elif '\n' in  line:
            ### Comment
            annotations[-1].comment += line
        else:
            raise Exception("ERROR: The boox annotations txt file contain unrecognisible line")

    return annotations
