"""Inline terminal_data.json into terminal_template.html -> powerpath_terminal.html"""
from pathlib import Path
T = Path(__file__).resolve().parents[1] / "terminal"
d = (T / "terminal_data.json").read_text().replace("</", "<\\/").replace("NaN", "null")
(T / "powerpath_terminal.html").write_text((T / "terminal_template.html").read_text().replace("__DATA__", d))
print("wrote", T / "powerpath_terminal.html")
