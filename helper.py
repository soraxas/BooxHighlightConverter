import fitz
from pdfrw import PdfDict, PdfArray, PdfName


class TextNotFoundException(Exception):
    pass
class MultipleInstancesException(Exception):
    pass
class FallbackFailedException(Exception):
    pass
class PossibleErrorException(Exception):
    pass

TOKENS_MIN_LENGTH = 2
SAME_LINE_TOL = 1.5

def createHighlight(points, color = [1,0.92,0.23], author=None, contents=None):
    newHighlight = PdfDict()
    newHighlight.F = 4
    newHighlight.Type = PdfName('Annot')
    newHighlight.Subtype = PdfName('Highlight')
    if author:
        newHighlight.T = author
    newHighlight.C = color
    if contents:
        newHighlight.Contents = contents
    newHighlight.indirect = True

#############################################################
### Search for bounding coordinates
#############################################################
    botLeft_x = float('inf')
    botLeft_y = float('inf')
    topRight_x = 0.0
    topRight_y = 0.0

    quad_pts = []
    for (x1, y1, x2, y2) in points:
        # this quadpoints specified PDF definition of rect box
        quad_pts.extend([x1, y2, x2, y2, x1, y1, x2, y1])
        botLeft_x = min(botLeft_x, x1, x2)
        botLeft_y = min(botLeft_y, y1, y2)
        topRight_x = max(topRight_x, x1, x2)
        topRight_y = max(topRight_y, y1, y2)

    newHighlight.QuadPoints = PdfArray(quad_pts)
    newHighlight.Rect = PdfArray([botLeft_x, botLeft_y,
                                  topRight_x, topRight_y])
    return newHighlight


def addAnnot(pdfrw_page, annot):
    """Add annotations to page, create an array if none exists yet"""
    if pdfrw_page.Annots is None:
        pdfrw_page.Annots = PdfArray()
    pdfrw_page.Annots.append(annot)

def pdfrw_quadpoint_to_fitz_rect(pts):
    origin = 0
    rects = []
    while origin < len(pts):
        (x1, y1, x2, y2) = pts[origin+0], pts[origin+5], pts[origin+6], pts[origin+1]
        rects.append(fitz.Rect(x1, y1, x2, y2))
        origin += 8
    return rects


class PDFTextSearch:
    def __init__(self, doc_name):
        self.doc = fitz.open(doc_name)

    def getQuadpoints(self, page_num, text, hit_max=16, ignore_short_width=4, extract=True):
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
            tb = page.getTextBlocks()
            consecutive_results = None
            i = 0
            for tb in page.getTextBlocks():
                if i >= len(rects):
                    break  # DONE
                tbRect = fitz.Rect(tb[0], tb[1], tb[2], tb[3])
                if tbRect.contains(rects[i]):
                    while i < len(rects):
                        if rects[i].width < ignore_short_width:
                            # Do not include this short line in highlighting
                            rects.pop(i)
                        if consecutive_results is None:
                            consecutive_results = 'started'
                        elif consecutive_results == 'end':
                            raise MultipleInstancesException("Possible multiple search results. The results are not consecutive")
                        # 'FOUNDDDDD!!!!!!
                        i += 1
                        if i >= len(rects) or not tbRect.contains(rects[i]):
                            break
                else:
                    if consecutive_results is 'started':
                        consecutive_results = 'end'

            # if reaching this point, all result must have been matched. If not, error
            if i < len(rects):
                raise PossibleErrorException("ERROR! Not all result been vertified.")
        if not extract:
            return rects
        merged = self.mergeTokens(rects)
        return self.invertCoordinates(merged, self.page_height(page_num))


    def fallbackGetQuadpoints(self, page_num, text, hit_max=16, ignore_short_width=4):
        """Search for the given text in the page. Raise exception if more than one result found"""
        tokens = []
        def add(w):
            """Helper functino to add w to tokens (and check length before doing so)"""
            if len(w) <= 2:
                print("  WARN: VERY SHORT token: '{}'! Ignoring this token...".format(w))
                return
            tokens.extend(self.getQuadpoints(page_num, w, hit_max, ignore_short_width, extract=False))
        def getToken(line):
            """Given line, return the splited sentence before and after the first occurance of an escape char"""
            idx, skiped_word = self.unicodeIdx(line)
            if idx < 0:
                return line, ''
            print("  INFO: Ignoring unicode '{}' from: '{}'".format(skiped_word, line))
            ws = line.split(' ')
            return ' '.join(ws[:idx]), ' '.join(ws[idx+1:])
        def addRemainingWords(line):
            # add all remaining words into list
            while len(line.split(' ')) > TOKENS_MIN_LENGTH:
                ws, line = getToken(line)
                try:
                    add(ws)
                except TextNotFoundException as e:
                    print("  WARN: Skipping '{}' as it was not found".format(ws))

        for i, line in enumerate(text.split('\n')):
            line = line.rstrip()
            if i == 0:
                # first few words
                if self.unicodeIdx(line) != -1 and self.unicodeIdx(line) <= 3:
                    raise FallbackFailedException("Escaped character too close to beginning tokens")
                ws, line = getToken(line)
                add(ws)
                addRemainingWords(line)
            else:
                addRemainingWords(line)
        merged = self.mergeTokens(tokens)
        return self.invertCoordinates(merged, self.page_height(page_num))

    def annot_exists(self, page_num, annot):
        """Given an annot in pdfrw, determine if it already exists by utilising fitz."""
        page = self.doc[page_num]
        pageAnnot = page.firstAnnot
        # need to change pdfrw's rect coor to fits fitz's coordinate *by inverting)
        pendingAnnots = [fitz.Rect(x) for x in self.invertCoordinates(pdfrw_quadpoint_to_fitz_rect(annot.QuadPoints), self.page_height(page_num))]
        # We consider the two given annots are the same if all the sub-parts of the pending annots intersects one of the annot that we are checking
        # (We cannot simply use contains because the coordinates data are slightly off and hence unreliable)
        while pageAnnot:
            # inverted
            if all(pageAnnot.rect.intersects(a) for a in pendingAnnots):
                return True
            # else we continue to check next annot
            pageAnnot = pageAnnot.next                        # get next annot on page

        return False

    def page_height(self, page_num):
        page = self.doc[page_num]
        return page.bound().y1

    @staticmethod
    def mergeTokens(annot_tokens):
        """Try to merge the broken tokens together, with full line width"""
        if len(annot_tokens) < 2:
            # no need to merge len = 1
            return annot_tokens
        def sameline(r1, r2):
            """Determine if r1 and r2 are on the same line"""
            tol = SAME_LINE_TOL
            if (abs(r1.y0 - r2.y0) < tol and
                abs(r1.y1 - r2.y1) < tol):
                return True
            return False
        def mergeColumnTokens(tokens):
            # loop through to find left most & right most boarder
            leftMost = float('inf')
            rightMost = 0
            for t in tokens:
                leftMost = min(leftMost, t.x0, t.x1)
                rightMost = max(rightMost, t.x0, t.x1)
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
                    new_lines.append(fitz.Rect(line[0].x0, bot, rightMost, top))
                elif i == len(lines) - 1:
                    new_lines.append(fitz.Rect(leftMost, bot, line[-1].x1, top))
                else:
                    new_lines.append(fitz.Rect(leftMost, bot, rightMost, top))
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
            return mergeColumnTokens(annot_tokens)

        firstcol_merged_tokens = mergeColumnTokens(double_column[0])
        secondcol_merged_tokens = mergeColumnTokens(double_column[1])
        firstcol_merged_tokens.extend(secondcol_merged_tokens)
        return firstcol_merged_tokens

    @staticmethod
    def invertCoordinates(rects, page_height):
        """
        TO work around the different coordinate system in fitz and pdfrw. The x-axis
        are same but the y-axis are opposite to each other. One starts at top and one starts
        at bottom
        """
        # convert from top left bot right -- to -- bot left top right
        # this is for compliance of convention in PDF
        rects = [(r.x0, r.y1, r.x1, r.y0) for r in rects]
        # the coordinate system in fitz and pdfrw are inverted. need to invert back with "page_height - y"
        # this is for converting between fitz and pdfrw system
        return [(r[0], page_height - r[1], r[2], page_height - r[3]) for r in rects]

    @staticmethod
    def unicodeIdx(text):
        """Return the index of word (within the line) that contain escape char \\x"""
        text = repr(text)[1:-1]
        for i, word in enumerate(text.split(' ')):
            if "\\x" in word:
                return i, word
        return -1, None
