import fitz
from pdfrw import PdfDict, PdfArray, PdfName


class TextNotFoundException(Exception):
    pass
class MultipleInstancesException(Exception):
    pass
class FallbackFailedException(Exception):
    pass


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
    botLeft_x = 99999.0
    botLeft_y = 99999.0
    topRight_x = 0.0
    topRight_y = 0.0

    quad_pts = []
    for (x1, y1, x2, y2) in points:
        quad_pts.append(x1)
        quad_pts.append(y2)
        quad_pts.append(x2)
        quad_pts.append(y2)
        quad_pts.append(x1)
        quad_pts.append(y1)
        quad_pts.append(x2)
        quad_pts.append(y1)
        botLeft_x = min(botLeft_x, x1); botLeft_x = min(botLeft_x, x2)
        botLeft_y = min(botLeft_y, y1); botLeft_y = min(botLeft_y, y2)
        topRight_x = max(topRight_x, x1); topRight_x = max(topRight_x, x2)
        topRight_y = max(topRight_y, y1); topRight_y = max(topRight_y, y2)

    newHighlight.QuadPoints = PdfArray(quad_pts)
    newHighlight.Rect = PdfArray([
                                    botLeft_x,
                                    botLeft_y,
                                    topRight_x,
                                    topRight_y
                                    ])
    return newHighlight


def addAnnot(page, annot):
    """Add annotations to page, create an array if none exists yet"""
    if page.Annots is None:
        page.Annots = PdfArray()
    page.Annots.append(annot)


class PDFTextSearch:
    def __init__(self, doc_name):

        self.doc = fitz.open(doc_name)

    def getQuadpoints(self, page_num, text, hit_max=16, ignore_short_width=4, extract=True):
        """Search for the given text in the page. Raise exception if more than one result found"""
        page = self.doc[page_num]
        page_height = page.bound().y1

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
                raise Exception("ERROR! Not all result been vertified.")
        if not extract:
            return rects
        merged = self.mergeTokens(rects)
        return self.invertCoordinates(merged, page_height)


    @staticmethod
    def invertCoordinates(rects, page_height):
        # convert from top left bot right -- to -- bot left top right
        rects = [(r.x0, r.y1, r.x1, r.y0) for r in rects]
        # the coordinate system in fitz and pdfrw are inverted. need to invert back with "page_height - y"
        return [(r[0], page_height - r[1], r[2], page_height - r[3]) for r in rects]

    def fallbackGetQuadpoints(self, page_num, text, hit_max=16, ignore_short_width=4):
        """Search for the given text in the page. Raise exception if more than one result found"""
        page = self.doc[page_num]
        page_height = page.bound().y1
        words = []
        tokens = []

        def add(w):
            if len(w) <= 2:
                raise Exception("VERY SHORT token!")
            tokens.extend(self.getQuadpoints(page_num, w, hit_max, ignore_short_width, extract=False))
            words.append(w)

        def getToken(line):
            """Given w, return the splited sentence before and after the first occurance of escape char"""
            idx, skip_word = self.unicodeIdx(line)
            if idx < 0:
                return line, ''
            print("INFO: Ignoring unicode '{}' from: '{}'".format(skip_word, line))
            ws = line.split(' ')
            return ' '.join(ws[:idx]), ' '.join(ws[idx+1:])

        # first few words
        for i, line in enumerate(text.split('\n')):
            line = line.rstrip()
            if i == 0:
                if self.unicodeIdx(line) != -1 and self.unicodeIdx(line) <= 4:
                    raise FallbackFailedException("Escaped character too close to beginning tokens")
                ws, line = getToken(line)
                add(ws)
                while len(line) > 2:
                    ws, line = getToken(line)
                    try:
                        add(ws)
                    except TextNotFoundException as e:
                        print("WARN: Skipping '{}' as it was not found".format(ws))
            else:
                while len(line) > 2:
                    ws, line = getToken(line)
                    add(ws)

        merged = self.mergeTokens(tokens)
        return self.invertCoordinates(merged, page_height)

    @staticmethod
    def mergeTokens(tokens):
        """Try to merge the broken tokens together, with full line width"""
        if len(tokens) < 2:
            return tokens
        def sameline(r1, r2):
            tol = 1.5
            if (abs(r1.y0 - r2.y0) < tol and
                abs(r1.y1 - r2.y1) < tol):
                return True
            return False

        # loop through to find left most & right most
        leftMost = 99999.9
        rightMost = 0
        for t in tokens:
            if leftMost > t.x0:
                leftMost = t.x0
            if leftMost > t.x1:
                leftMost = t.x1
            if rightMost < t.x0:
                rightMost = t.x0
            if rightMost < t.x1:
                rightMost = t.x1

        lines = []
        for i, t in enumerate(tokens):
            if i == 0:
                lines.append([t])  # first
            else:
                # determine if it's same line as before
                if sameline(lines[-1][0], t):
                    lines[-1].append(t)
                else:
                    lines.append([t])
############################################################
##                 NOW WE DO THE MERGING                 ##
############################################################
        new_lines = []
        for i, line in enumerate(lines):
            bot = 9999.9
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

    @staticmethod
    def unicodeIdx(text):
        text = repr(text)[1:-1]
        for i, word in enumerate(text.split(' ')):
            if "\\x" in word:
                return i, word
        return -1, None
