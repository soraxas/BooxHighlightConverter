import os
import re

class Anno:
    def __init__(self):
        self.page = None
        self.text = ''
        self.comment = None

def readAnnotations(pdf_path):
    # folder that holds the annotations
    path_name = os.path.splitext(pdf_path)[0]
    base_name_with_ext = os.path.basename(pdf_path)
    base_name = os.path.splitext(base_name_with_ext)[0]

    anno_file = open(os.path.join(path_name, base_name + '-annotation.txt'))
    begining_anno = True
    ended = False
    annotations = []
    for line in anno_file.readlines():
        #################
        ##  ~REPLACE~  ##
        #################
        # this indicate some token that the program cannot recognise (as place holder)
        if "\xef\xbf\xbe" in line:
            line = line.replace("\xef\xbf\xbe", '-\n')
        ###########################
        if begining_anno:
            ### Page line + Comment
            annotations.append(Anno())

            begining_anno = False
            matchObj = re.match( r'(?:Page )([0-9]+)\s{1,2}(.*)?\n', line)

            if not matchObj:
                raise Exception("Error in parsing first line")

            annotations[-1].page = matchObj.group(1)
            annotations[-1].comment = matchObj.group(2)
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
            annotations[-1].page = int(annotations[-1].page) - 1  # NOTE this -1 because in the program index starts at 0
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
