import re

from io import StringIO
from urllib.parse import urlparse

#
# Adapted from:
# https://github.com/huntingb/gemtext-html-converter
#
# Uses StringIO instead of files
#

# A dictionary that maps regex to match at the beginning of gmi lines to
# their corresponding HTML tag names. Used by convert_single_line().
tags_dict = {
    r"^# (.*)": "h1",
    r"^## (.*)": "h2",
    r"^### (.*)": "h3",
    r"^\* (.*)": "li",
    r"^> (.*)": "blockquote",
    r"^=>\s*(\S+)(\s+.*)?": "a"
}

imageExts = ["png", "jpg", "jpeg", "gif", "svg", "webp"]


def convert_single_line(gmi_line):
    for pattern in tags_dict.keys():
        match = re.match(pattern, gmi_line)
        if match:
            tag = tags_dict[pattern]
            groups = match.groups()
            if tag == "a":
                href = groups[0]

                if len(groups) > 1 and isinstance(groups[1], str):
                    inner_text = groups[1].strip()
                else:
                    inner_text = href

                url = urlparse(href)

                # Show images if the extension matches
                for ext in imageExts:
                    if url.path and url.path.endswith(f'.{ext}'):
                        return inner_text, f"<p><img src='{href}'></img></p>"

                return inner_text, \
                    f"""<p><{tag} title='{href}'
                    href='{href}'>{inner_text}</{tag}></p>"""
            else:
                inner_text = groups[0].strip()
                return inner_text, f"<{tag}>{inner_text}</{tag}>"

    url = urlparse(gmi_line)
    if url and url.scheme in ['gemini', 'ipfs'] and url.netloc:
        return None, f"<p><a href='{url.geturl()}'>{url.geturl()}</a></p>"

    return None, f"<p>{gmi_line}</p>"


def gemTextToHtml(gmi: str):
    html = StringIO()
    preformat = False
    in_list = False
    title = None

    for line in gmi.split('\n'):
        if len(line):
            if line.startswith("```") or line.endswith("```"):
                preformat = not preformat
                repl = "<pre>" if preformat else "</pre>"
                html.write(re.sub(r"```", repl, line))
            elif preformat:
                html.write(line)
            else:
                inner, html_line = convert_single_line(line)

                if not title and (html_line.startswith("<h1>") or
                                  html_line.startswith("<h2>") or
                                  html_line.startswith("<h3>")):
                    # First heading used wins
                    title = inner

                if html_line.startswith("<li>"):
                    if not in_list:
                        in_list = True
                        html.write("<ul>\n")
                    html.write(html_line)
                elif in_list:
                    in_list = False
                    html.write("</ul>\n")
                    html.write(html_line)
                else:
                    html.write(html_line)

        html.write("\n")

    if in_list:
        # Case where a list is the last thing in a document ?
        html.write("</ul>\n")

    return html.getvalue(), title
