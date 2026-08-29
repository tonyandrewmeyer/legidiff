"""Turn a PCO Act XML document into a tree of Markdown files.

The whole point of the exercise is diff quality, so the rendering rules exist
to keep unrelated versions byte-identical:

* One file per section, named after the section's *label*, so a section keeps
  its file (and so ``git blame`` keeps its history) across renumbering of the
  Act around it.
* One sentence per line, so an amendment that swaps a few words shows up as a
  one-line diff instead of a reflowed paragraph.
* No element ids and no hrefs. PCO regenerates those identifiers between
  versions; including them would make every file differ in every version.
"""

import collections
import dataclasses
import datetime
import re
import unicodedata
import xml.etree.ElementTree as ET

# Inline elements we mark up; everything else inline is passed through as text.
INLINE_WRAPPERS = {
    'emphasis': ('*', '*'),
    'def-term': ('**', '**'),
    'struckoutwords': ('~~', '~~'),
}

# Inline containers whose text we keep but whose markup we ignore.
DROP_INLINE = {'citation', 'leg-title', 'extref', 'intref', 'insertwords', 'cf-ref'}


# Tags whose text we dropped on the floor, counted so that running the
# renderer over a wide sample tells us what the older DTDs use.
DROPPED: collections.Counter[str] = collections.Counter()


def slugify(text: str) -> str:
    """A lowercase, hyphenated, ASCII form of *text*, for use in a filename."""
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode()
    text = re.sub(r'[^A-Za-z0-9]+', '-', text).strip('-').lower()
    return text[:70].rstrip('-')


# Older Acts spell their schedule numbers out.
ORDINALS = {
    'first': 1,
    'second': 2,
    'third': 3,
    'fourth': 4,
    'fifth': 5,
    'sixth': 6,
    'seventh': 7,
    'eighth': 8,
    'ninth': 9,
    'tenth': 10,
    'eleventh': 11,
    'twelfth': 12,
    'thirteenth': 13,
    'fourteenth': 14,
    'fifteenth': 15,
}


def sort_key(label: str) -> str:
    """A sortable, stable filename stem for a provision label.

    Labels look like ``7``, ``2A``, ``312M``, ``1AA``, or (in older Acts)
    ``First Schedule``. Zero-padding the numeric head makes lexical order
    match legislative order.
    """
    label = label.strip()
    first_word = re.split(r'[^A-Za-z]', label, maxsplit=1)[0].lower()
    if first_word in ORDINALS:
        return f'{ORDINALS[first_word]:04d}'
    if not label:
        return '9999'
    # Zero-pad every run of digits, so "CW 6" sorts before "CW 52B" and "7"
    # before "167". Labels that start with a letter keep that letter first.
    padded = re.sub(r'\d+', lambda m: f'{int(m[0]):04d}', label)
    return slugify(padded) or '9999'


_SENTENCE = re.compile(r"(?<=[.:;])\s+(?=[\"'(A-Z])")


def sentences(text: str) -> list[str]:
    """Split a run of text into one line per sentence, conservatively."""
    parts = _SENTENCE.split(text)
    merged: list[str] = []
    for part in parts:
        # Don't split after an initial or a numbered abbreviation ("No. 4").
        if merged and re.search(r'(\b[A-Z]|\bNo|\bs|\bcl)\.$', merged[-1]):
            merged[-1] = f'{merged[-1]} {part}'
        else:
            merged.append(part)
    return [p for p in (m.strip() for m in merged) if p]


def inline(element: ET.Element) -> str:
    """Flatten an element's mixed content to Markdown, ids and hrefs discarded."""
    out: list[str] = []
    if element.tag == 'field':
        return '______'
    if element.text:
        out.append(element.text)
    for child in element:
        rendered = inline(child)
        if child.tag in INLINE_WRAPPERS and rendered.strip():
            open_, close = INLINE_WRAPPERS[child.tag]
            rendered = f'{open_}{rendered.strip()}{close}'
        out.append(rendered)
        if child.tail:
            out.append(child.tail)
    return re.sub(r'[ \t\n]+', ' ', ''.join(out))


@dataclasses.dataclass
class Amendment:
    """One history note: who changed what, when."""

    provision: str
    operation: str
    when: datetime.date | None
    amending_act: str
    note: str


def parse_note_date(text: str) -> datetime.date | None:
    """The date a history note carries, or None when it has none we can read."""
    for fmt in ('%d %B %Y', '%d %b %Y'):
        try:
            return datetime.datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def note_text(note: ET.Element, tag: str) -> str:
    """The text of one child of a history note, or the empty string."""
    element = note.find(tag)
    return inline(element).strip() if element is not None else ''


def amendments(root: ET.Element) -> list[Amendment]:
    """Every amendment recorded in the document's history notes."""
    return [
        Amendment(
            provision=note_text(note, 'amended-provision'),
            operation=note_text(note, 'amending-operation'),
            when=parse_note_date(note_text(note, 'amendment-date')),
            amending_act=note_text(note, 'amending-leg'),
            note=inline(note).strip(),
        )
        for note in root.iter('history-note')
    ]


class Renderer:
    """Renders block-level XML into Markdown lines."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def blank(self) -> None:
        """Start a new block, unless the output already ends in a blank line."""
        if self.lines and self.lines[-1] != '':
            self.lines.append('')

    def paragraph(self, text: str, indent: int = 0) -> None:
        """Write *text* as a paragraph, one sentence per line."""
        text = text.strip()
        if not text:
            return
        pad = ' ' * indent
        self.blank()
        self.lines.extend(f'{pad}{line}' for line in sentences(text))

    def bullet(self, label: str, text: str, depth: int) -> None:
        """A labelled provision: ``- **(3)** text``, nested by depth."""
        pad = '  ' * depth
        first, *rest = sentences(text) or ['']
        self.blank()
        self.lines.append(f'{pad}- **({label})** {first}'.rstrip())
        self.lines.extend(f'{pad}  {line}' for line in rest)

    def block(self, element: ET.Element, depth: int = 0) -> None:
        """Write one block element, and everything nested inside it."""
        tag = element.tag
        if tag in ('subprov', 'label-para', 'def-para', 'schedule-prov', 'clause', 'item'):
            label_element = element.find('label')
            label = inline(label_element).strip() if label_element is not None else ''
            body = [child for child in element if child is not label_element]
            self.labelled(label, body, depth)
        elif tag == 'para':
            self.mixed(element, depth)
        elif tag == 'text':
            self.paragraph(inline(element), depth * 2)
        elif tag in (
            'subprov.crosshead',
            'crosshead',
            'label-para.crosshead',
            'subheading',
            'ird-crosshead',
        ):
            self.blank()
            self.lines.append(f'### {inline(element).strip()}')
        elif re.fullmatch(r'head[1-6]|preamble\.headlev[1-6]', tag):
            # The older DTD's structural headings, mostly inside schedules.
            self.heading(element, depth)
        elif tag == 'form':
            self.heading(element, depth, level='##')
        elif tag == 'eqn':
            # An Income Tax Act formula, then its "where—" variable list.
            for line in element.findall('eqn-line'):
                self.blank()
                self.lines.append(f'> {inline(line).strip()}')
            for child in element:
                if child.tag != 'eqn-line':
                    self.block(child, depth)
        elif tag == 'variable-def':
            variable = self._child_text(element, 'variable')
            body = [child for child in element if child.tag != 'variable']
            self.labelled(variable, body, depth)
        elif tag == 'term.list':
            terms = ', '.join(inline(term).strip() for term in element.findall('term'))
            if terms:
                self.blank()
                self.lines.append(f'*Defined in this Act: {terms}*')
        elif tag in ('sig.para', 'sig.officer', 'enactment', 'preamble'):
            self.paragraph(inline(element), depth * 2)
        elif tag == 'cf':
            pass  # compare-references; surfaced with the provision's notes
        elif tag in ('table', 'legtable'):
            self.table(element, depth)
        elif tag in ('example', 'editorial-note', 'quote.in'):
            self.quoted(element, depth)
        elif tag == 'prov':
            # A nested provision: a clause inside a schedule.
            label = self._child_text(element, 'label')
            heading = self._child_text(element, 'heading')
            self.blank()
            self.lines.append(f'## {label}{": " + heading if heading else ""}'.rstrip())
            for child in element:
                if child.tag not in ('label', 'heading'):
                    self.block(child, 0)
        elif tag == 'empowering-prov':
            self.blank()
            self.lines.append(f'*Made under {inline(element).strip()}*')
        elif tag == 'notes':
            for note in element.iter('history-note'):
                self.blank()
                self.lines.append(f'> {inline(note).strip()}')
        elif element.find('heading') is not None or element.find('label') is not None:
            # Any other container that titles itself - parts and nested
            # schedules inside a schedule, reprint notes, amendment groups.
            self.heading(element, depth)
        else:
            if (element.text or '').strip():
                DROPPED[tag] += 1
                self.paragraph(inline(element), depth * 2)
            else:
                for child in element:
                    self.block(child, depth)

    def heading(self, element: ET.Element, depth: int, level: str = '###') -> None:
        """A structural heading with its own label, plus whatever it contains."""
        label = self._child_text(element, 'label')
        heading = self._child_text(element, 'heading')
        text = f'{label}{": " if label and heading else ""}{heading}'.strip()
        if text:
            self.blank()
            self.lines.append(f'{level} {text}')
        for child in element:
            if child.tag not in ('label', 'heading'):
                self.block(child, depth)

    @staticmethod
    def _child_text(element: ET.Element, tag: str) -> str:
        child = element.find(tag)
        return inline(child).strip() if child is not None else ''

    def labelled(self, label: str, body: list[ET.Element], depth: int) -> None:
        """Emit ``- **(a)** first text`` then anything nested under it."""
        lead = ''
        rest: list[ET.Element] = []
        for child in body:
            if not lead and child.tag in ('para', 'text'):
                text_element = child.find('text') if child.tag == 'para' else child
                if text_element is not None:
                    lead = inline(text_element)
                    rest.extend(c for c in child if c is not text_element)
                    continue
            rest.append(child)
        if label:
            self.bullet(label, lead, depth)
            depth += 1
        else:
            # Unnumbered provisions (many older sections have no subsections)
            # read better as plain prose than as a bullet with an empty label.
            self.paragraph(lead, depth * 2)
        for child in rest:
            self.block(child, depth)

    def mixed(self, element: ET.Element, depth: int) -> None:
        """Write the children of an element that holds blocks."""
        for child in element:
            self.block(child, depth)

    def quoted(self, element: ET.Element, depth: int) -> None:
        """Write an amending Act's quoted text as a block quote."""
        inner = Renderer()
        inner.mixed(element, 0)
        self.blank()
        self.lines.extend(f'> {line}'.rstrip() for line in inner.lines)

    def table(self, element: ET.Element, depth: int) -> None:
        """Write a table as a Markdown table."""
        rows = [
            [inline(cell).strip() for cell in row.findall('entry')] for row in element.iter('row')
        ]
        if not rows:
            return
        width = max(len(row) for row in rows)
        self.blank()
        header, *body = rows
        header += [''] * (width - len(header))
        self.lines.append('| ' + ' | '.join(header) + ' |')
        self.lines.append('| ' + ' | '.join(['---'] * width) + ' |')
        for row in body:
            row += [''] * (width - len(row))
            self.lines.append('| ' + ' | '.join(row) + ' |')

    def text(self) -> str:
        """Everything written so far, with trailing blank lines removed."""
        while self.lines and self.lines[-1] == '':
            self.lines.pop()
        return '\n'.join(self.lines) + '\n'


def render_notes(element: ET.Element) -> list[str]:
    """The history/compare notes that hang off a provision."""
    lines: list[str] = []
    notes = element.find('notes')
    if notes is None:
        return lines
    history = [inline(note).strip() for note in notes.iter('history-note')]
    compare = [inline(note).strip() for note in notes.iter('cf')]
    if history:
        lines += ['', '## History', '']
        lines += [f'- {note}' for note in history]
    if compare:
        lines += ['', '## Compare', '']
        lines += [f'- {note}' for note in compare]
    return lines


def render_provision(element: ET.Element, kind: str = 'Section') -> str:
    """Render one provision, heading and all, as the body of its own file."""
    label_element = element.find('label')
    heading_element = element.find('heading')
    label = inline(label_element).strip() if label_element is not None else ''
    heading = inline(heading_element).strip() if heading_element is not None else ''

    # Older Acts label their schedules "SECOND SCHEDULE"; don't say it twice.
    prefix = '' if kind.lower() in label.lower() else f'{kind} '
    lines = [f'# {prefix}{label}{": " + heading if heading else ""}'.strip()]
    status = element.get('deletion-status')
    if status:
        lines += ['', f'*[{status}]*']

    renderer = Renderer()
    for child in element:
        if child in (label_element, heading_element) or child.tag == 'notes':
            continue
        renderer.block(child, 0)
    body = renderer.text().strip()
    if body:
        lines += ['', body]
    lines += render_notes(element)
    return '\n'.join(lines).rstrip() + '\n'


@dataclasses.dataclass
class Document:
    """A rendered version of an Act: relative path -> file content."""

    title: str
    slug: str
    as_at: str
    year: str
    number: str
    files: dict[str, str] = dataclasses.field(default_factory=dict)
    source_path: str = ''
    collisions: list[str] = dataclasses.field(default_factory=list)
    amendments: list[Amendment] = dataclasses.field(default_factory=list)


def render(xml: bytes) -> Document:
    """Render one version of an Act into the files that make up its directory."""
    # S314: the XML comes from the PCO over TLS, not from a user.
    root = ET.fromstring(xml)  # noqa: S314
    title_element = root.find('cover/title')
    title = inline(title_element).strip() if title_element is not None else 'Untitled'
    document = Document(
        title=title,
        slug=slugify(title),
        as_at=(
            root.get('date.as.at') or root.get('date.first.valid') or root.get('date.assent') or ''
        ),
        year=root.get('year', ''),
        number=root.get('act.no', ''),
        amendments=amendments(root),
    )

    contents: list[str] = []

    def titles(element: ET.Element) -> tuple[str, str]:
        label = element.find('label')
        heading = element.find('heading')
        return (
            inline(label).strip() if label is not None else '',
            inline(heading).strip() if heading is not None else '',
        )

    def unique(path: str, element: ET.Element, context: str = '') -> str:
        """Keep two provisions with the same number and heading apart.

        Acts do contain them: a repealed provision beside its replacement,
        or a schedule whose parts each number their clauses from 1. Prefer a
        suffix that says which one this is (the part it sits in, or that it's
        the repealed one), and fall back to document order, which is stable
        between versions either way.
        """
        if path not in document.files:
            return path
        document.collisions.append(path)
        stem, _, extension = path.rpartition('.')
        for suffix in (context, 'repealed' if element.get('deletion-status') else ''):
            if suffix and f'{stem}-{suffix}.{extension}' not in document.files:
                return f'{stem}-{suffix}.{extension}'
        number = 2
        while f'{stem}-{number}.{extension}' in document.files:
            number += 1
        return f'{stem}-{number}.{extension}'

    def add_provision(
        element: ET.Element,
        folder: str,
        kind: str,
        sink: list[str],
        base: str = '',
        context: str = '',
    ) -> None:
        label, heading = titles(element)
        stem = f'{sort_key(label)}-{slugify(heading)}'.rstrip('-')
        path = unique(f'{folder}/{stem}.md', element, context)
        document.files[path] = render_provision(element, kind)
        status = ' *(repealed)*' if element.get('deletion-status') else ''
        name = f'{kind} {label}{": " + heading if heading else ""}'
        sink.append(f'- [{name}]({path[len(base) :]}){status}')

    def collect(
        container: ET.Element,
        folder: str,
        kind: str,
        sink: list[str],
        base: str = '',
        level: int = 3,
        context: str = '',
    ) -> list[ET.Element]:
        """Walk a body or a schedule's provisions.

        Each provision becomes its own file; parts and crossheads become
        headings in the contents. Anything else is handed back to the caller
        to render inline.
        """
        leftovers: list[ET.Element] = []
        for child in container:
            if child.tag == 'prov':
                add_provision(child, folder, kind, sink, base, context)
            elif child.tag in ('part', 'subpart'):
                label, heading = titles(child)
                name = f'{child.tag.title()} {label}{": " + heading if heading else ""}'
                sink += ['', f'{"#" * min(level, 6)} {name.rstrip(": ")}', '']
                for note in child.iterfind('notes/history/history-note'):
                    sink += [f'> {inline(note).strip()}', '']
                leftovers += collect(
                    child,
                    folder,
                    kind,
                    sink,
                    base,
                    level + 1,
                    context or f'{child.tag}-{sort_key(label)}',
                )
            elif child.tag == 'schedule.group':
                # A schedule of its own inside a schedule: the forms
                # attached to a set of rules, typically. Give each one a file.
                for nested in child.findall('schedule'):
                    label, heading = titles(nested)
                    sink += [
                        '',
                        f'{"#" * min(level, 6)} Schedule {label}'
                        f'{": " + heading if heading else ""}'.rstrip(': '),
                        '',
                    ]
                    add_provision(nested, folder, 'Schedule', sink, base)
            elif child.tag in ('crosshead', 'ird-crosshead'):
                sink += ['', f'*{inline(child).strip()}*', '']
            elif child.tag in ('label', 'heading', 'contents', 'notes'):
                pass
            else:
                leftovers.append(child)
        return leftovers

    def rendered(elements: list[ET.Element]) -> str:
        renderer = Renderer()
        for element in elements:
            renderer.block(element, 0)
        return renderer.text().strip()

    def add_schedule(schedule: ET.Element) -> None:
        """One file per schedule, unless it has clauses, then one per clause.

        Some schedules are books: schedule 2 of the Judicature Act 1908 was
        the whole High Court Rules. Splitting them the way sections are split
        keeps an amendment to one rule to a diff of one small file.
        """
        label, heading = titles(schedule)
        stem = f'{sort_key(label)}-{slugify(heading)}'.rstrip('-')
        prefix = '' if 'schedule' in label.lower() else 'Schedule '
        name = f'{prefix}{label}{": " + heading if heading else ""}'.strip()
        status = ' *(repealed)*' if schedule.get('deletion-status') else ''

        provisions = schedule.find('schedule.provisions')
        clauses = list(provisions.iter('prov')) if provisions is not None else []
        if not clauses:
            path = unique(f'schedules/{stem}.md', schedule)
            document.files[path] = render_provision(schedule, 'Schedule')
            contents.append(f'- [{name}]({path}){status}')
            return

        folder = f'schedules/{stem}'
        index = unique(f'{folder}/index.md', schedule)
        folder = index.rsplit('/', 1)[0]
        document.files[index] = ''  # claim the path before the clauses fill in
        kind = (schedule.get('prov-type') or 'clause').title()

        inner: list[str] = []
        leftovers = collect(provisions, folder, kind, inner, f'{folder}/')
        for child in schedule:
            if child.tag not in ('label', 'heading', 'notes', 'contents', 'schedule.provisions'):
                leftovers.append(child)

        lines = [f'# {name}']
        if status:
            lines += ['', '*[repealed]*']
        preamble = rendered(leftovers)
        if preamble:
            lines += ['', preamble]
        lines += ['', '## Contents', '', *inner]
        lines += render_notes(schedule)
        document.files[index] = '\n'.join(lines).rstrip() + '\n'
        contents.append(f'- [{name}]({index}){status}')

    body = root.find('body')
    body_leftovers: list[ET.Element] = []
    if body is not None:
        body_leftovers = collect(body, 'sections', 'Section', contents)

    schedules = root.find('schedule.group')
    if schedules is not None:
        contents += ['', '### Schedules', '']
        for schedule in schedules.findall('schedule'):
            add_schedule(schedule)

    front = root.find('front')
    if front is not None:
        document.files['front.md'] = f'# {title}: long title\n\n{rendered(list(front))}\n'

    end = root.find('end/end.reprint-note')
    if end is not None:
        document.files['reprint-notes.md'] = f'# {title}: reprint notes\n\n{rendered(list(end))}\n'

    index_lines = [
        f'# {title}',
        '',
        f'- Act {document.year} No {document.number}',
        '',
        '## Contents',
        '',
        *contents,
    ]
    extra = rendered(body_leftovers)
    if extra:
        index_lines += ['', '## Other content', '', extra]
    document.files['index.md'] = '\n'.join(index_lines).rstrip() + '\n'
    return document
