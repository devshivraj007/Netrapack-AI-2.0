"""Spatial grouping of OCR words into meaningful text blocks.

Two strategies, used together:

  1. Line clustering: group words that sit on the same horizontal band into
     lines, then group vertically-close lines that look related (e.g. a
     manufacturer name followed by two or three address lines) into one block.

  2. Phrase-anchored grouping: curved surfaces (cans, bottles) distort line
     spacing so pure geometry is unreliable. We look for anchor phrases like
     "Mfg by", "Marketed by", "Pvt Ltd" and gather nearby text around them.

Part D item 3 (multi-line address merging) is implemented here: a name line
plus its following address lines plus the PIN-code line are merged into ONE
block string before anything is handed to the rule engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .reader import Word

# Anchor phrases that typically introduce a manufacturer/packer block.
ANCHOR_PHRASES = [
    "mfg by", "mfd by", "manufactured by", "marketed by", "packed by",
    "pkd by", "imported by", "mkt by", "mfg", "pvt ltd", "private limited",
    "ltd", "llp", "inc",
]

_PIN_RE = re.compile(r"\b\d{6}\b")  # Indian PIN code


@dataclass
class Line:
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in sorted(self.words, key=lambda w: w.left))

    @property
    def top(self) -> float:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> float:
        return max(w.bottom for w in self.words)

    @property
    def cy(self) -> float:
        return sum(w.cy for w in self.words) / len(self.words)

    @property
    def height(self) -> float:
        return sum(w.height for w in self.words) / len(self.words)


@dataclass
class Block:
    lines: list[Line] = field(default_factory=list)
    source: str = "line_cluster"  # or "phrase_anchor"

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines).strip()


def cluster_words_into_lines(words: list[Word]) -> list[Line]:
    """Group words that share a horizontal band into lines, by geometry.

    We cluster on the vertical centre (cy): words whose centres fall within
    roughly half a line-height of each other belong to the same line. This is
    more robust than trusting Tesseract's line_num under --psm 6 (which can
    lump an entire label into one "block"), and it correctly separates a label
    into its real visual lines so each field keyword stays on its own line.
    """
    if not words:
        return []

    ordered = sorted(words, key=lambda w: w.cy)
    median_h = sorted(w.height for w in ordered)[len(ordered) // 2]
    tolerance = max(median_h * 0.6, 8.0)

    lines: list[Line] = []
    current: list[Word] = [ordered[0]]
    current_cy = ordered[0].cy
    for w in ordered[1:]:
        if abs(w.cy - current_cy) <= tolerance:
            current.append(w)
            # Running average keeps the band stable as we add words.
            current_cy = sum(x.cy for x in current) / len(current)
        else:
            lines.append(Line(words=current))
            current = [w]
            current_cy = w.cy
    lines.append(Line(words=current))
    return lines


def merge_related_lines(lines: list[Line], gap_factor: float = 1.6) -> list[Block]:
    """Merge vertically-close lines into blocks.

    Two consecutive lines join the same block when the vertical gap between
    them is small relative to text height (i.e. normal line spacing). A large
    gap starts a new block.
    """
    if not lines:
        return []

    blocks: list[Block] = []
    current = Block(lines=[lines[0]])
    for prev, nxt in zip(lines, lines[1:]):
        gap = nxt.top - prev.bottom
        allowed = max(prev.height, nxt.height) * gap_factor
        if gap <= allowed:
            current.lines.append(nxt)
        else:
            blocks.append(current)
            current = Block(lines=[nxt])
    blocks.append(current)
    return blocks


def phrase_anchored_blocks(lines: list[Line], window: int = 3) -> list[Block]:
    """Build blocks around anchor phrases for curved-surface fallback.

    For each line that contains an anchor phrase, gather that line plus up to
    `window` following lines (where an address usually continues) into a block.
    """
    blocks: list[Block] = []
    n = len(lines)
    used: set[int] = set()
    for i, line in enumerate(lines):
        low = line.text.lower()
        if any(anchor in low for anchor in ANCHOR_PHRASES):
            grp = [line]
            j = i + 1
            while j < n and (j - i) <= window:
                grp.append(lines[j])
                used.add(j)
                # Stop after we hit a PIN code (address usually ends there).
                if _PIN_RE.search(lines[j].text):
                    break
                j += 1
            blocks.append(Block(lines=grp, source="phrase_anchor"))
    return blocks


def merge_manufacturer_address(block_text: str) -> str:
    """Part D #3: collapse a multi-line name+address+PIN into one clean line.

    Joins lines with commas, removes duplicate whitespace, and makes sure a
    trailing 6-digit PIN stays attached to the block rather than dangling.
    """
    # Normalise internal line breaks to single spaces first.
    text = re.sub(r"[\r\n]+", " ", block_text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


@dataclass
class GroupedText:
    blocks: list[Block]
    lines: list[str]  # individual OCR text lines (for per-line field extraction)
    full_text: str
    manufacturer_block: str  # best-guess merged manufacturer/address block


def group_text(words: list[Word]) -> GroupedText:
    """Produce grouped blocks and a best-guess manufacturer block.

    Combines line-cluster blocks with phrase-anchored blocks. The manufacturer
    block is chosen as the phrase-anchored block if one exists (most reliable
    signal), else the longest line-cluster block that contains an anchor.

    Individual OCR lines are also returned so the field extractor can match
    keyword anchors line-by-line (each label field usually lives on its own
    line), rather than against merged multi-line blocks.
    """
    lines = cluster_words_into_lines(words)
    line_texts = [ln.text for ln in lines if ln.text.strip()]
    line_blocks = merge_related_lines(lines)
    anchor_blocks = phrase_anchored_blocks(lines)

    all_blocks = line_blocks + anchor_blocks
    full_text = "\n".join(line_texts).strip()

    manufacturer_block = ""
    if anchor_blocks:
        # Prefer the longest anchored block (name + full address).
        manufacturer_block = max(
            (b.text for b in anchor_blocks), key=len, default=""
        )
    else:
        anchored_line_blocks = [
            b.text for b in line_blocks
            if any(a in b.text.lower() for a in ANCHOR_PHRASES)
        ]
        if anchored_line_blocks:
            manufacturer_block = max(anchored_line_blocks, key=len)

    manufacturer_block = merge_manufacturer_address(manufacturer_block)
    return GroupedText(
        blocks=all_blocks,
        lines=line_texts,
        full_text=full_text,
        manufacturer_block=manufacturer_block,
    )
