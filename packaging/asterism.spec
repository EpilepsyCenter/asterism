# PyInstaller recipe for ASTERISM (macOS .app, Windows and Linux folders).
#   .venv/bin/pyinstaller packaging/asterism.spec --noconfirm
# Output in dist/: ASTERISM.app (macOS) or ASTERISM/ (Windows, Linux).
import os
import sys

sys.path.insert(0, os.path.abspath("."))
from asterism import __version__  # noqa: E402

ROOT = os.path.abspath(".")
ASSETS = os.path.join(ROOT, "asterism", "app", "assets")
ICON = {"darwin": "asterism.icns", "win32": "asterism.ico"}.get(sys.platform, "asterism.png")

datas = [
    (os.path.join(ROOT, "asterism", "help", "pages"), "asterism/help/pages"),
    (ASSETS, "asterism/app/assets"),
    (os.path.join(ROOT, "LICENSE"), "."),
    (os.path.join(ROOT, "THIRD_PARTY_NOTICES.md"), "."),
]

# Not used by the app: test-only libraries and Qt modules we never import
excludes = [
    "matplotlib", "pingouin", "sklearn", "seaborn", "tkinter", "IPython", "pytest", "pypdf", "PIL",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtGraphs", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech",
    "PySide6.QtHttpServer", "PySide6.QtOpenGLWidgets",
]

a = Analysis(
    [os.path.join(ROOT, "packaging", "launch.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=["PySide6.QtSvg", "PySide6.QtNetwork", "statsmodels.formula.api"],
    excludes=excludes,
    noarchive=False,
)
# Qt pieces pulled in only by plugins we don't use (virtual keyboard, PDF image format)
_unused = ("QtQuick", "QtQml", "QtVirtualKeyboard", "QtPdf", "qtvirtualkeyboard", "libqpdf", "qpdf.dll",
           "Qt6Quick", "Qt6Qml", "Qt6VirtualKeyboard", "Qt6Pdf", "libQt6Quick", "libQt6Qml",
           "libQt6VirtualKeyboard", "libQt6Pdf")
a.binaries = [b for b in a.binaries if not any(u in b[0] for u in _unused)]
a.datas = [d for d in a.datas if not any(u in d[0] for u in _unused)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="ASTERISM",
    console=False,
    icon=os.path.join(ASSETS, ICON),
    version=os.path.join(ROOT, "packaging", "windows_version.txt") if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ASTERISM", strip=False, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="ASTERISM.app",
        icon=os.path.join(ASSETS, "asterism.icns"),
        bundle_identifier="io.github.epilepsycenter.asterism",
        version=__version__,
        info_plist={
            "CFBundleName": "ASTERISM",
            "CFBundleDisplayName": "ASTERISM",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,          # follow light and dark mode
            "LSMinimumSystemVersion": "12.0",
            "NSHumanReadableCopyright": "© 2026 Marco Ledri. Free for noncommercial use (PolyForm Noncommercial 1.0.0). Not affiliated with GraphPad.",
            "CFBundleDocumentTypes": [
                {"CFBundleTypeName": "ASTERISM Project", "CFBundleTypeRole": "Editor",
                 "LSHandlerRank": "Owner", "CFBundleTypeIconFile": "asterism.icns",
                 "LSItemContentTypes": ["io.github.epilepsycenter.asterism.project"]},
                {"CFBundleTypeName": "Prism Project", "CFBundleTypeRole": "Viewer",
                 "LSHandlerRank": "Alternate", "CFBundleTypeExtensions": ["prism", "pzfx"]},
            ],
            "UTExportedTypeDeclarations": [
                {"UTTypeIdentifier": "io.github.epilepsycenter.asterism.project",
                 "UTTypeDescription": "ASTERISM Project",
                 "UTTypeConformsTo": ["public.data", "public.content"],
                 "UTTypeIconFile": "asterism.icns",
                 "UTTypeTagSpecification": {"public.filename-extension": ["asterism"]}},
            ],
        },
    )
