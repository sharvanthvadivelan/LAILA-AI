from html import escape
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound


def code(text, lang, *args):
    try:
        result = highlight(text, get_lexer_by_name(lang), HtmlFormatter(nowrap=True))
    except ClassNotFound:
        result = escape(text)
    return (
        '<pre><span class="code-lang">'
        + escape(lang or "code")
        + "</span><code>"
        + result
        + "</code></pre>"
    )


md = MarkdownIt("commonmark", {"html": False, "highlight": code}).enable("table")
# Remote images are blocked, so model output cannot trigger network requests.
md.renderer.rules["image"] = (
    lambda tokens, idx, options, env: "<span>[Image: "
    + escape(tokens[idx].content)
    + "]</span>"
)


def render_markdown(text):
    return md.render(text)
