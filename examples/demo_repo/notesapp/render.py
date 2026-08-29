from jinja2 import Environment, Markup

NOTE_TEMPLATE = "<article><h2>{{ title }}</h2><div class=\"body\">{{ body }}</div></article>"


def trusted_html(text):
    return Markup(text)


def build_environment():
    return Environment(autoescape=True)


def render_note(title, body, allow_html=False):
    template = build_environment().from_string(NOTE_TEMPLATE)
    content = trusted_html(body) if allow_html else body
    return template.render(title=title, body=content)


def render_many(notes):
    return "\n".join(render_note(note["title"], note["body"]) for note in notes)
