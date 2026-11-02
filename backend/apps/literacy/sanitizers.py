import nh3

SAFE_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

SAFE_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title"},
}

SAFE_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_markdown(body: str | None) -> str:
    """Sanitizes markdown / HTML content using nh3 (Rust-based ammonia).

    Strips unsafe HTML tags (<script>, <style>, <iframe>, <object>, <embed>),
    on* event handlers (onerror=, onload=), and dangerous URL schemes (javascript:)
    while preserving markdown formatting and safe HTML tags per D113.
    """
    if not body:
        return ""

    return nh3.clean(
        body,
        tags=SAFE_TAGS,
        attributes=SAFE_ATTRIBUTES,
        url_schemes=SAFE_URL_SCHEMES,
        link_rel="noopener noreferrer",
    )
