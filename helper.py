import fitz
from pdfrw import PdfDict, PdfArray, PdfName


def create_highlight(points, color=(1, 0.92, 0.23), author=None, contents=None):
    """Given Quad points, create a highligh object in standard pdf format."""
    new_highlight = PdfDict()
    new_highlight.F = 4
    new_highlight.Type = PdfName('Annot')
    new_highlight.Subtype = PdfName('Highlight')
    if author:
        new_highlight.T = author
    new_highlight.C = color
    if contents:
        new_highlight.Contents = contents
    new_highlight.indirect = True

    #############################################################
    ### Search for bounding coordinates
    #############################################################
    bot_left_x = float('inf')
    bot_left_y = float('inf')
    top_right_x = 0.0
    top_right_y = 0.0

    quad_pts = []
    for (x1, y1, x2, y2) in points:
        # this quadpoints specified PDF definition of rect box
        quad_pts.extend([x1, y2, x2, y2, x1, y1, x2, y1])
        bot_left_x = min(bot_left_x, x1, x2)
        bot_left_y = min(bot_left_y, y1, y2)
        top_right_x = max(top_right_x, x1, x2)
        top_right_y = max(top_right_y, y1, y2)

    new_highlight.QuadPoints = PdfArray(quad_pts)
    new_highlight.Rect = PdfArray([bot_left_x, bot_left_y,
                                   top_right_x, top_right_y])
    return new_highlight

def add_annot(pdfrw_page, annot):
    """Add annotations to page, create an array if none exists yet"""
    if pdfrw_page.Annots is None:
        pdfrw_page.Annots = PdfArray()
    pdfrw_page.Annots.append(annot)

def pdfrw_quadpoint_to_fitz_rect(pts):
    """Convert pdfrw quadpoints into fitz rect format (from one library to another)."""
    origin = 0
    rects = []
    while origin < len(pts):
        (x1, y1, x2, y2) = pts[origin+0], pts[origin+5], pts[origin+6], pts[origin+1]
        rects.append(fitz.Rect(x1, y1, x2, y2))
        origin += 8
    return rects
