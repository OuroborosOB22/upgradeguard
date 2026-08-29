from notesapp.render import render_many, render_note, trusted_html


def test_plain_body_is_escaped():
    output = render_note("Notes", "<script>alert(1)</script>")
    assert "&lt;script&gt;" in output
    assert "<script>" not in output


def test_title_is_escaped():
    output = render_note("<b>hi</b>", "body")
    assert "&lt;b&gt;hi&lt;/b&gt;" in output


def test_trusted_html_is_kept():
    output = render_note("Notes", "<em>real</em>", allow_html=True)
    assert "<em>real</em>" in output


def test_trusted_html_marks_string_safe():
    assert hasattr(trusted_html("<b>x</b>"), "__html__")


def test_render_many_joins_notes():
    notes = [{"title": "one", "body": "first"}, {"title": "two", "body": "second"}]
    output = render_many(notes)
    assert output.count("<article>") == 2
