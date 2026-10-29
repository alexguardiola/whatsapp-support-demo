import re
import unicodedata

_WORD = re.compile(r"[a-z0-9]+")


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def slugify(text: str) -> str:
    return "-".join(_WORD.findall(fold(text)))


def words(text: str) -> list[str]:
    return _WORD.findall(fold(text))
