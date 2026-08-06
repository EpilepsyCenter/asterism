"""ASTERISM — Dash entry point (browser).

    python app.py            # dev server at http://127.0.0.1:8050
    python -m asterism_dash.desktop   # native desktop window (needs desktop deps)
"""

from asterism_dash.main import app

if __name__ == "__main__":
    app.run(debug=True, port=8050)
