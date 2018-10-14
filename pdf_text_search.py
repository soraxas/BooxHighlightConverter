"""
For searching text in a pdf file.
"""
import logging
import fitz
from helper import pdfrw_quadpoint_to_fitz_rect

_LOGGER = logging.getLogger()

TOKENS_MIN_LENGTH = 2
SAME_LINE_TOL = 1.5

class TextNotFoundException(Exception):
    """Exception for text not found in pdf."""
    pass

class MultipleInstancesException(Exception):
    """Exception for multiple possible instances found in pdf."""
    pass

class FallbackFailedException(Exception):
    """Exception for fallback method of pdf text search fails as well."""
    pass

class PossibleErrorException(Exception):
    """Exception for a possible unforseen error."""
    pass

class PDFTextSearch:
    """Represent a class that search text from a pdf."""

    def __init__(self, doc_name):
        self.doc = fitz.open(doc_name)

    def get_quadpoints(self, page_num, text, hit_max=16, ignore_short_width=4, extract=True):
        """Search for the given text in the page. Raise exception if more than one result found"""
        page = self.doc[page_num]
        rects = page.searchFor(text, hit_max=hit_max)
        if len(rects) < 1:
            raise TextNotFoundException("No search result found: {}".format(text))
        if len(rects) > 1:
            # We detect error very naively...... But at least it's better than none.
            # We detect via checking if the results are consecutive lines. If they are
            # it is most likely it is a single result with multiline spanning. If not,
            # most likely the searching text is too short and result in many lines having
            # the same sequence of word.
            textblock = page.getTextBlocks()
            consecutive_results = None
            i = 0
            for textblock in page.getTextBlocks():
                if i >= len(rects):
                    break  # DONE
                textblock_rect = fitz.Rect(textblock[0], textblock[1], textblock[2], textblock[3])
                if textblock_rect.contains(rects[i]):
                    while i < len(rects):
                        if rects[i].width < ignore_short_width:
                            # Do not include this short line in highlighting
                            rects.pop(i)
                        if consecutive_results is None:
                            consecutive_results = 'started'
                        elif consecutive_results == 'end':
                            raise MultipleInstancesException(
                                "Possible multiple search results. The results are not consecutive")
                        # 'FOUNDDDDD!!!!!!
                        i += 1
                        if i >= len(rects) or not textblock_rect.contains(rects[i]):
                            break
                else:
                    if consecutive_results == 'started':
                        consecutive_results = 'end'

            # if reaching this point, all result must have been matched. If not, error
            if i < len(rects):
                raise PossibleErrorException("ERROR! Not all result been vertified.")
        if not extract:
            return rects
        merged = self.merge_tokens(rects)
        return self.invert_coordinates(merged, self.page_height(page_num))


    def fallback_get_quadpoints(self, page_num, text, hit_max=16, ignore_short_width=4):
        """
        Search for the given text in the page. Raise exception if more than one result found.
        This fallback method breaks the entire text into chunks of tokens, and ignore tokens that
        cannot be recognised. Therefore, it is more robust as it ignores a part of tokens for
        better finding text, and also does its best to detect error.
        """
        tokens = []
        def add(words):
            """Helper functino to add w to tokens (and check length before doing so)"""
            if len(words) <= 2:
                _LOGGER.debug("VERY SHORT token: '%s'! Ignoring this token...", words)
                return
            tokens.extend(self.get_quadpoints(page_num, words, hit_max,
                                              ignore_short_width, extract=False))
        def get_token(line):
            """Given line, return the splited sentence before and after the first
            occurance of an escape char"""
            idx, skiped_word = self.unicode_idx(line)
            if idx < 0:
                return line, ''
            _LOGGER.debug("Ignoring unicode '%s' from: '%s'", skiped_word, line)
            words = line.split(' ')
            return ' '.join(words[:idx]), ' '.join(words[idx+1:])
        def add_remaining_words(line):
            """Add all remaining words into list."""
            while len(line.split(' ')) > TOKENS_MIN_LENGTH:
                words, line = get_token(line)
                try:
                    add(words)
                except TextNotFoundException:
                    _LOGGER.debug("Skipping '%s' as it was not found", words)

        for i, line in enumerate(text.split('\n')):
            line = line.rstrip()
            if i == 0:
                # first few words
                if self.unicode_idx(line) != -1 and self.unicode_idx(line) <= 3:
                    raise FallbackFailedException("Escaped character too close to beginning tokens")
                words, line = get_token(line)
                add(words)
                add_remaining_words(line)
            else:
                add_remaining_words(line)
        merged = self.merge_tokens(tokens)
        return self.invert_coordinates(merged, self.page_height(page_num))

    def annot_exists(self, page_num, annot):
        """Given an annot in pdfrw, determine if it already exists by utilising fitz."""
        page = self.doc[page_num]
        page_annot = page.firstAnnot
        # need to change pdfrw's rect coor to fits fitz's coordinate *by inverting)
        pending_annots = [fitz.Rect(x) for x in self.invert_coordinates(
            pdfrw_quadpoint_to_fitz_rect(annot.QuadPoints), self.page_height(page_num))]
        """We consider the two given annots are the same if all the sub-parts of the pending
        annots intersects one of the annot that we are checking. (We cannot simply use
        contains because the coordinates data are slightly off and hence unreliable)"""
        while page_annot:
            # inverted
            if all(page_annot.rect.intersects(a) for a in pending_annots):
                return True
            # else we continue to check next annot
            page_annot = page_annot.next                        # get next annot on page

        return False

    def page_height(self, page_num):
        """Return the page height of given page."""
        page = self.doc[page_num]
        return page.bound().y1

    @staticmethod
    def merge_tokens(annot_tokens):
        """Try to merge the broken tokens together, with full line width"""
        if len(annot_tokens) < 2:
            # no need to merge len = 1
            return annot_tokens
        def sameline(l1, l2):
            """Determine if l1 and l2 are on the same line"""
            tol = SAME_LINE_TOL
            if (abs(l1.y0 - l2.y0) < tol and
                    abs(l1.y1 - l2.y1) < tol):
                return True
            return False
        def merge_column_tokens(tokens):
            """Loop through to find left most & right most boarder."""
            left_most = float('inf')
            right_most = 0
            for t in tokens:
                left_most = min(left_most, t.x0, t.x1)
                right_most = max(right_most, t.x0, t.x1)
            lines = []
            for i, t in enumerate(tokens):
                if i == 0:
                    lines.append([t])  # first line no need to check previous line
                else:
                    # determine if it's same line as before
                    if sameline(lines[-1][0], t):
                        # append to previous line
                        lines[-1].append(t)
                    else:
                        # create a new line
                        lines.append([t])
            ###########################
            ## NOW WE DO THE MERGING ##
            ###########################
            new_lines = []
            for i, line in enumerate(lines):
                bot = float('inf')
                top = 0
                for l in line:
                    bot = min(bot, l.y0)
                    top = max(top, l.y1)
                if i == 0:
                    new_lines.append(fitz.Rect(line[0].x0, bot, right_most, top))
                elif i == len(lines) - 1:
                    new_lines.append(fitz.Rect(left_most, bot, line[-1].x1, top))
                else:
                    new_lines.append(fitz.Rect(left_most, bot, right_most, top))
            return new_lines

        # detect if the highlights spans a double column
        is_double_column = False
        double_column = [[], []]
        double_column[0].append(annot_tokens[0])

        # filter the tokens that belong to different columns, and perform merge for each column
        for i in range(1, len(annot_tokens)):
            if not sameline(annot_tokens[i-1], annot_tokens[i]):
                if annot_tokens[i-1].y0 > annot_tokens[i].y0:
                    is_double_column = True
            if not is_double_column:
                double_column[0].append(annot_tokens[i])
            else:
                double_column[1].append(annot_tokens[i])
        if not is_double_column:
            return merge_column_tokens(annot_tokens)

        firstcol_merged_tokens = merge_column_tokens(double_column[0])
        secondcol_merged_tokens = merge_column_tokens(double_column[1])
        firstcol_merged_tokens.extend(secondcol_merged_tokens)
        return firstcol_merged_tokens

    @staticmethod
    def invert_coordinates(rects, page_height):
        """
        TO work around the different coordinate system in fitz and pdfrw. The x-axis
        are same but the y-axis are opposite to each other. One starts at top and one starts
        at bottom
        """
        # convert from top left bot right -- to -- bot left top right
        # this is for compliance of convention in PDF
        rects = [(r.x0, r.y1, r.x1, r.y0) for r in rects]
        # the coordinate system in fitz and pdfrw are inverted.
        # Need to invert back with "page_height - y"
        # this is for converting between fitz and pdfrw system
        return [(r[0], page_height - r[1], r[2], page_height - r[3]) for r in rects]

    @staticmethod
    def unicode_idx(text):
        """Return the index of word (within the line) that contain escape char \\x"""
        text = repr(text)[1:-1]
        for i, word in enumerate(text.split(' ')):
            if "\\x" in word:
                return i, word
        return -1, None
