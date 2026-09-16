import re

def validate_paper_id(paper_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", paper_id):
        raise ValueError("Paper ID must be 1-100 letters, digits, underscores or hyphens, starting with a letter or digit.")
    return paper_id
