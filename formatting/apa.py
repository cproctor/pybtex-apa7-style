import re

from pybtex.plugin import find_plugin
from pybtex.style.formatting import BaseStyle, toplevel
from pybtex.style.template import (
    field, first_of, href, join, optional, optional_field, sentence, tag,
    together, words, node, FieldIsMissing
)
from pybtex.richtext import Text, Symbol

firstlast = find_plugin('pybtex.style.names', 'firstlast')()

MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]

def format_pages(text):
    dash_re = re.compile(r'-+')
    pages = Text(Symbol('ndash')).join(text.split(dash_re))
    if re.search('[-‒–—―]', str(text)):
        return Text("pp.", Symbol('nbsp'), pages)
    return Text("p.", Symbol('nbsp'), pages)

pages = field('pages', apply_func=format_pages)

def parse_iso_date(value):
    """
    Parses a Zotero/bibtex-style ISO date string ("YYYY", "YYYY-MM", or
    "YYYY-MM-DD") into (year, month name, day) parts. Any part not present
    in `value` is returned as None.
    """
    if not value:
        return None, None, None
    match = re.match(r'^\s*(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?', str(value))
    if not match:
        return None, None, None
    year, month, day = match.groups()
    month_name = MONTH_NAMES[int(month) - 1] if month else None
    day_num = str(int(day)) if day else None
    return year, month_name, day_num

@node
def apa_date(children, context, **kwargs):
    """
    Formats a date with whatever granularity is available: year, year and
    month, or year, month, and day. Prefers explicit `year`/`month`/`day`
    fields, but falls back to parsing a Zotero-style `date` field (e.g.
    "2020-05-03") when those aren't present.
    """
    assert not children

    fields = context['entry'].fields
    year, month, day = fields.get('year'), fields.get('month'), fields.get('day')
    if not year:
        fallback_year, fallback_month, fallback_day = parse_iso_date(fields.get('date'))
        year = year or fallback_year
        month = month or fallback_month
        day = day or fallback_day
    if not year:
        raise FieldIsMissing('year', context['entry'])
    if day and day.isdigit():
        day = str(int(day))  # normalize "05" -> "5"

    if month and day:
        return Text(f"{year}, {month} {day}")
    elif month:
        return Text(f"{year}, {month}")
    else:
        return Text(year)

date = apa_date()

@node
def apa_names(children, context, role, **kwargs):
    """
    Returns formatted names as an APA compliant reference list citation.
    """
    assert not children

    try:
        persons = context['entry'].persons[role]
    except KeyError:
        raise FieldIsMissing(role, context['entry'])

    style = context['style']

    if len(persons) > 20:
        formatted_names = [style.format_name(
            person, style.abbreviate_names) for person in persons[:20]]
        formatted_names += [Text("et al.")]
        return join(sep=', ')[formatted_names].format_data(context)
    else:
        formatted_names = [style.format_name(
            person, style.abbreviate_names) for person in persons]
        return join(sep=', ', sep2=', & ', last_sep=', & ')[
            formatted_names].format_data(context)

@node
def editor_names(children, context, with_suffix=True, **kwargs):
    """
    Returns formatted editor names for inbook.
    """
    assert not children

    try:
        editors = context['entry'].persons['editor']
    except KeyError:
        raise FieldIsMissing('editor', context['entry'])

    formatted_names = [
        firstlast.format(editor, True) for editor in editors]

    if with_suffix:
        return words[
            join(sep=', ', sep2=', & ', last_sep=', & ')[formatted_names],
            "(Eds.)" if len(editors) > 1 else "(Ed.)"
        ].format_data(context)

    return join(sep=', ', sep2=', & ', last_sep=', & ')[
        formatted_names
    ].format_data(context)

class APAStyle(BaseStyle):
    name = 'apa7'
    default_name_style = 'lastfirst'
    default_sorting_style = 'author_year_title'
    default_label_style = 'apa7'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.abbreviate_names = True

    def format_names(self, role, as_sentence=True):
        formatted_names = apa_names(role)
        if as_sentence:
            return sentence(capfirst=False)[formatted_names]
        else:
            return formatted_names

    def format_author_or_editor_and_date(self, e):
        if 'author' in e.persons and 'editor' in e.persons:
            return sentence(sep=' ')[
                self.format_names('author'), 
                self.format_date(e),
                self.format_editor(e, as_sentence=False)
            ]
        elif 'author' in e.persons:
            return sentence(sep=' ')[
                self.format_names('author'), 
                self.format_date(e),
            ]
        else:
            return sentence(sep=' ')[
                self.format_editor(e, as_sentence=False),
                self.format_date(e),
            ]

    def format_editor(self, e, as_sentence=True):
        editors = self.format_names('editor', as_sentence=False)
        if 'editor' not in e.persons:
            # when parsing the template, a FieldIsMissing exception
            # will be thrown anyway; no need to do anything now,
            # just return the template that will throw the exception
            return editors
        if len(e.persons['editor']) > 1:
            word = '(Eds.)'
        else:
            word = '(Ed.)'
        result = join(sep=' ')[editors, word]
        if as_sentence:
            return sentence[result]
        else:
            return result

    def format_volume(self, e, for_article=False):
        prefix = "Vol."
        if for_article:
            return join[
                tag('em')[field('volume')],
                optional['(', field('number'), ')'],
            ]
        else:
            return optional[together[prefix, field('volume')]]

    def format_title(self, e, which_field, as_sentence=True):
        formatted_title = field(
            which_field, apply_func=lambda text: text.capitalize()
        )
        if as_sentence:
            return sentence[formatted_title]
        else:
            return formatted_title

    def format_btitle(self, e, which_field, as_sentence=True):
        formatted_title = tag('em')[field(which_field)]
        if as_sentence:
            return sentence[formatted_title]
        else:
            return formatted_title

    def resolve_web_ref(self, e, which_field):
        """
        Returns the URL that `format_url`/`format_eprint`/`format_pubmed`/
        `format_doi` would generate for `which_field`, or None if the field
        isn't present. Used to detect when the same URL is duplicated across
        multiple identifier fields (common in Zotero exports, where `url`,
        `eprint`, and `doi` sometimes all end up holding the same DOI link).
        """
        value = e.fields.get(which_field)
        if not value:
            return None
        value = value.strip()
        if which_field == 'url':
            return value
        if which_field == 'doi':
            return 'https://doi.org/' + value
        if which_field == 'pubmed':
            return 'https://www.ncbi.nlm.nih.gov/pubmed/' + value
        if which_field == 'eprint':
            # Some exports (e.g. Zotero) put a full URL in `eprint` instead
            # of a bare arXiv id; don't mangle it into a broken arxiv.org
            # link if it's already absolute.
            if re.match(r'^https?://', value):
                return value
            return 'https://arxiv.org/abs/' + value
        return None

    def format_web_refs(self, e):
        doi_url = self.resolve_web_ref(e, 'doi')
        refs = []
        for which_field, formatter in [
            ('url', self.format_url),
            ('eprint', self.format_eprint),
            ('pubmed', self.format_pubmed),
        ]:
            resolved = self.resolve_web_ref(e, which_field)
            if resolved and resolved == doi_url:
                continue  # duplicates the DOI link; skip it
            refs.append(optional[formatter(e)])
        refs.append(optional[self.format_doi(e)])
        return sentence(add_period=False)[refs]

    def format_url(self, e):
        return words[
            'URL:',
            href[
                field('url', raw=True),
                field('url', raw=True)
            ]
        ]

    def format_pubmed(self, e):
        return href[
            join[
                'https://www.ncbi.nlm.nih.gov/pubmed/',
                field('pubmed', raw=True)
            ],
            join[
                'PMID:',
                field('pubmed', raw=True)
            ]
        ]

    def format_doi(self, e):
        return href[
            join[
                'https://doi.org/',
                field('doi', raw=True)
            ],
            join[
                'doi:',
                field('doi', raw=True)
            ]
        ]

    def format_eprint(self, e):
        value = e.fields.get('eprint', '').strip()
        if re.match(r'^https?://', value):
            # already a full URL; don't prepend the arxiv.org prefix
            return href[
                field('eprint', raw=True),
                join[
                    'arXiv:',
                    field('eprint', raw=True)
                ]
            ]
        return href[
            join[
                'https://arxiv.org/abs/',
                field('eprint', raw=True)
            ],
            join[
                'arXiv:',
                field('eprint', raw=True)
            ]
        ]

    def format_date(self, e):
        return sentence[
            join["(", first_of[optional[date], "n.d."], ")"]
        ]

    def get_article_template(self, e):
        volume_and_pages = first_of[
            optional[
                join[
                    self.format_volume(e, for_article=True),
                    optional[', ', field('pages')]
                ],
            ],
            pages,
        ]
        if 'author' in e.persons:
            return toplevel[
                self.format_names('author'),
                self.format_date(e),
                self.format_title(e, 'title'),
                sentence[
                    tag('em')[field('journal')],
                    optional[volume_and_pages],
                ],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]
        else:
            return toplevel[
                self.format_title(e, 'title'),
                self.format_date(e),
                sentence[
                    tag('em')[field('journal')],
                    optional[volume_and_pages],
                ],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]

        return template

    def get_book_template(self, e):
        if 'author' in e.persons or 'editor' in e.persons:
            return toplevel[
                self.format_author_or_editor_and_date(e),
                sentence(sep=' ')[
                    self.format_btitle(e, 'title'),
                    optional[
                        sentence[
                            optional[field('edition'), ' ed.'],
                            self.format_volume(e),
                        ]
                    ]
                ],
                sentence()[
                    field('publisher'),
                ],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]
        else:
            return toplevel[
                self.format_btitle(e, 'title'),
                self.format_date(e),
                sentence(sep=' ')[
                    optional[
                        sentence[
                            optional[field('edition'), ' ed.'],
                            self.format_volume(e),
                        ]
                    ]
                ],
                sentence()[
                    field('publisher'),
                ],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]

    def get_booklet_template(self, e):
        if 'author' in e.persons:
            return toplevel[
                self.format_names('author'),
                self.format_date(e),
                self.format_title(e, 'title'),
                sentence[optional_field('address')],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]
        else:
            return toplevel[
                self.format_title(e, 'title'),
                self.format_date(e),
                sentence[optional_field('address')],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]

    def get_inbook_template(self, e):
        if 'author' in e.persons:

            return toplevel[
                self.format_names('author'),
                self.format_date(e),
                self.format_title(e, 'title'),
                sentence(sep=' ')[
                    optional["In ", editor_names(), ","],
                    self.format_btitle(e, 'booktitle', as_sentence=False),
                    optional[
                        join[
                            "(",
                            sentence(add_period=False)[
                                optional[field('edition'), ' ed.'],
                                self.format_volume(e),
                                pages,
                            ],
                            ")"
                        ]
                    ]
                ],
                sentence()[
                    field('publisher'),
                ],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]
        else:
            return toplevel[
                self.format_title(e, 'title'),
                self.format_date(e),
                sentence(sep=' ')[
                    optional["In ", editor_names(), ","],
                    self.format_btitle(e, 'booktitle', as_sentence=False),
                    optional[
                        join[
                            "(",
                            sentence(add_period=False)[
                                optional[field('edition'), ' ed.'],
                                self.format_volume(e),
                                pages,
                            ],
                            ")"
                        ]
                    ]
                ],
                sentence()[
                    field('publisher'),
                ],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]

    
    def get_incollection_template(self, e):
        if 'author' in e.persons or 'editor' in e.persons:
            return toplevel[
                self.format_author_or_editor_and_date(e),
                self.format_title(e, 'title'),
                sentence(sep=' ')[
                    self.format_btitle(e, 'booktitle', as_sentence=False),
                    optional["(", pages, ")"]
                ],
                sentence()[
                    optional_field('publisher'),
                ],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]
        else:
            return toplevel[
                self.format_title(e, 'title'),
                self.format_date(e),
                sentence(sep=' ')[
                    self.format_btitle(e, 'booktitle', as_sentence=False),
                    optional["(", pages, ")"]
                ],
                sentence()[
                    optional_field('publisher'),
                ],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]

    def get_inproceedings_template(self, e):
        if 'author' in e.persons:
            return toplevel[
                self.format_author_or_editor_and_date(e),
                self.format_title(e, 'title'),
                sentence(sep=' ')[
                    self.format_btitle(e, 'booktitle', as_sentence=False),
                    optional["(", pages, ")"]
                ],
                sentence[optional_field('publisher')],
                sentence[optional_field('note')],
                self.format_web_refs(e)
            ]
        else:
            return toplevel[
                self.format_title(e, 'title'),
                self.format_date(e),
                sentence(sep=' ')[
                    self.format_btitle(e, 'booktitle', as_sentence=False),
                    optional["(", pages, ")"]
                ],
                sentence[optional_field('publisher')],
                sentence[optional_field('note')],
                self.format_web_refs(e)
            ]
    def get_manual_template(self, e):
        if 'author' in e.persons:
            return toplevel[
                self.format_names('author'),
                self.format_date(e),
                self.format_btitle(e, 'title'),
                sentence[optional_field('address')],
                sentence[optional_field('note')],
                self.format_web_refs(e)
            ]
        else:
            return toplevel[
                self.format_btitle(e, 'title'),
                self.format_date(e),
                sentence[optional_field('address')],
                sentence[optional_field('note')],
                self.format_web_refs(e)
            ]

    def get_mastersthesis_template(self, e):
        return toplevel[
            sentence(sep=' ')[
                self.format_names('author'),
                self.format_date(e),
            ],
            sentence(sep=' ')[
                self.format_btitle(e, 'title', as_sentence=False),
                "(Master's thesis)"
            ],
            sentence[
                field('school'),
                optional_field('address'),
            ],
            sentence[optional_field('note')],
            self.format_web_refs(e),
        ]

    def get_misc_template(self, e):
        if 'author' in e.persons:
            return toplevel[
                self.format_names('author'),
                self.format_date(e),
                optional[self.format_btitle(e, 'title')],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]
        else:
            return toplevel[
                optional[self.format_btitle(e, 'title')],
                self.format_date(e),
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]

    def get_phdthesis_template(self, e):
        return toplevel[
            sentence(sep=' ')[
                self.format_names('author'),
                self.format_date(e),
            ],
            sentence(sep=' ')[
                self.format_btitle(e, 'title', as_sentence=False),
                "(Doctoral dissertation)"
            ],
            sentence[
                field('school'),
                optional_field('address'),
            ],
            sentence[optional_field('note')],
            self.format_web_refs(e),
        ]

    def get_proceedings_template(self, e):
        if 'editor' in e.persons:
            return toplevel[
                self.format_editor(e),
                self.format_date(e),
                self.format_btitle(e, 'title'),
                sentence[optional_field('publisher')],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]
        else:
            return toplevel[
                self.format_btitle(e, 'title'),
                self.format_date(e),
                sentence[optional_field('publisher')],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]

    def get_techreport_template(self, e):
        if 'author' in e.persons:
            return toplevel[
                self.format_names('author'),
                self.format_date(e),
                self.format_btitle(e, 'title'),
                sentence[field('institution')],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]
        else:
            return toplevel[
                self.format_btitle(e, 'title'),
                self.format_date(e),
                sentence[field('institution')],
                sentence[optional_field('note')],
                self.format_web_refs(e),
            ]

    def get_unpublished_template(self, e):
        if 'author' in e.persons:
            return toplevel[
                self.format_names('author'),
                self.format_date(e),
                self.format_btitle(e, 'title'),
                sentence[field('note')],
                self.format_web_refs(e),
            ]
        else:
            return toplevel[
                self.format_btitle(e, 'title'),
                self.format_date(e),
                sentence[field('note')],
                self.format_web_refs(e),
            ]
