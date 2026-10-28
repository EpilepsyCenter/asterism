# Third-party software in ASTERISM

ASTERISM itself is released under the MIT licence (see `LICENSE`). The packaged apps also
contain the following software, each under its own licence.

| Component | Licence | Source |
|---|---|---|
| Qt 6 and PySide6 (Qt for Python) | GNU LGPL v3 | https://www.qt.io, https://code.qt.io |
| Python | Python Software Foundation License | https://www.python.org |
| NumPy | BSD 3-Clause | https://numpy.org |
| SciPy | BSD 3-Clause | https://scipy.org |
| pandas | BSD 3-Clause | https://pandas.pydata.org |
| statsmodels | BSD 3-Clause | https://www.statsmodels.org |
| patsy | BSD 2-Clause | https://github.com/pydata/patsy |
| openpyxl | MIT | https://openpyxl.readthedocs.io |
| xlrd | BSD | https://github.com/python-excel/xlrd |
| PyYAML | MIT | https://pyyaml.org |
| Lucide icons | ISC (see `asterism/app/assets/lucide/LICENSE`) | https://lucide.dev |

## Qt and the LGPL

ASTERISM uses Qt through PySide6 under the GNU Lesser General Public License v3. The Qt
libraries are included unmodified, as separate shared libraries inside the app (the
`PySide6` folder: `Qt*.framework` on macOS, `Qt6*.dll` on Windows, `libQt6*.so*` on Linux).
You may replace them with your own builds of the same Qt version. The Qt source code is
available from https://code.qt.io and https://download.qt.io. The LGPL v3 text is at
https://www.gnu.org/licenses/lgpl-3.0.html.

ASTERISM is not affiliated with, endorsed by or connected to GraphPad Software or Dotmatics.
"Prism" is their trademark; ASTERISM reads Prism files for interoperability.
