# Boox Highlights Converter

### Convert highlight annotations produced by Boox neoreader into standard PDF format

The original format created by neo-reader from boox eink reader are in txt and the standard export function
from reader create a non-standard pdf format. So I wrote this script to read in from the txt file produced
by neo-reader, and re-create those annotations (only highlights and comments for now) with help from 
`pdfrw` and `PyMuPDF`. You will need a `pyenv` virtualenv named as `pdf` (and install dependencies from `requirements.txt`)
if you want to use it in your system.
