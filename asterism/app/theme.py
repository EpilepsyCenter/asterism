"""App look shared with NED-Net: warm-paper palette, one desaturated cyan accent.

The tokens mirror NED-Net's style.css (--ned-*), so the two apps read as siblings.
NED-Net's oklch colours are converted to sRGB hex here; borders stay translucent
like the CSS. Controls are drawn by Fusion + one app stylesheet, so the look is
the same on macOS and Windows; the title bar, menu bar, file dialogs and system
font stay native. The theme follows the system light/dark setting live.
"""

from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette, QPen
from PySide6.QtWidgets import QApplication, QTabBar, QTabWidget

LIGHT = {
    "bg": "#f3f2ee",             # content canvas
    "sidebar": "#e8e7e2",        # project sidebar (source list)
    "chrome": "#f8f7f4",         # toolbar, status bar, dialogs
    "surface": "#fcfbf8",        # panels, tab panes, popups
    "surface_hover": "#e6e4dc",
    "field": "#ffffff",          # text fields, table cells
    "control_border": (20, 22, 28, 0.22),
    "border": (20, 22, 28, 0.10),
    "text": "#15171b",           # near-black, never pure
    "muted": "#55585f",
    "icon": "#3b3e44",           # default icon tint
    "accent": "#007d93",         # oklch(0.54 0.10 215)
    "accent_hover": "#006781",   # oklch(0.46 0.12 215)
    "accent_dim": "#acdae6",     # oklch(0.86 0.05 215)
    "success": "#429c5a",
    "warning": "#e18600",
    "danger": "#d73337",
    "purple": "#6a53bd",
    "on_accent": "#ffffff",
    "canvas": "#e8e7e2",         # behind the graph page
}

DARK = {
    "bg": "#0e1114",
    "sidebar": "#15191e",
    "chrome": "#13171b",
    "surface": "#161a1f",
    "surface_hover": "#1f252c",
    "field": "#1b2026",
    "control_border": (255, 255, 255, 0.16),
    "border": (255, 255, 255, 0.09),
    "text": "#e6e8ec",
    "muted": "#9ba2ad",
    "icon": "#c5cad2",
    "accent": "#62c8df",         # oklch(0.78 0.10 215)
    "accent_hover": "#7adff7",
    "accent_dim": "#005262",
    "success": "#69c27e",
    "warning": "#fc9f30",
    "danger": "#ff6f69",
    "purple": "#9e8afa",
    "on_accent": "#0b0d10",
    "canvas": "#0e1114",
}


class _Notifier(QObject):
    changed = Signal()


notifier = _Notifier()
_state = {"installed": False, "dark": False}


def is_dark() -> bool:
    return _state["dark"]


def tokens() -> dict:
    return DARK if _state["dark"] else LIGHT


def color(name: str) -> QColor:
    v = tokens()[name]
    if isinstance(v, tuple):
        r, g, b, a = v
        return QColor(r, g, b, round(a * 255))
    return QColor(v)


def mix(a, b, t: float) -> QColor:
    """Solid colour t of the way from a to b (token names or QColors)."""
    ca = color(a) if isinstance(a, str) else QColor(a)
    cb = color(b) if isinstance(b, str) else QColor(b)
    if cb.alpha() < 255:                       # translucent token: composite over a
        t, cb = t * cb.alphaF(), QColor(cb.red(), cb.green(), cb.blue())
    return QColor(round(ca.red() + (cb.red() - ca.red()) * t),
                  round(ca.green() + (cb.green() - ca.green()) * t),
                  round(ca.blue() + (cb.blue() - ca.blue()) * t))


def _css(v) -> str:
    if isinstance(v, QColor):
        return v.name() if v.alpha() == 255 else f"rgba({v.red()},{v.green()},{v.blue()},{v.alphaF():.3f})"
    if isinstance(v, tuple):
        r, g, b, a = v
        return f"rgba({r},{g},{b},{a})"
    return v


def _alpha(name: str, a: float) -> str:
    c = color(name)
    return f"rgba({c.red()},{c.green()},{c.blue()},{a})"


# --------------------------------------------------------------------- palette

def _palette() -> QPalette:
    t = tokens()
    p = QPalette()
    roles = {
        QPalette.Window: t["chrome"], QPalette.WindowText: t["text"],
        QPalette.Base: t["field"], QPalette.AlternateBase: mix("field", "text", 0.03),
        QPalette.Text: t["text"], QPalette.PlaceholderText: mix("field", "muted", 0.8),
        QPalette.Button: t["field"], QPalette.ButtonText: t["text"],
        QPalette.BrightText: t["on_accent"],
        QPalette.Highlight: t["accent"], QPalette.HighlightedText: t["on_accent"],
        QPalette.Link: t["accent"], QPalette.LinkVisited: t["accent_hover"],
        QPalette.ToolTipBase: t["surface"], QPalette.ToolTipText: t["text"],
        QPalette.Light: t["field"], QPalette.Midlight: t["surface_hover"],
        QPalette.Mid: mix("chrome", "control_border", 1.0), QPalette.Dark: t["muted"],
        QPalette.Shadow: "#000000",
    }
    for role, c in roles.items():
        p.setColor(role, QColor(c))
    p.setColor(QPalette.Accent, QColor(t["accent"]))
    dis = mix("chrome", "muted", 0.7)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, dis)
    p.setColor(QPalette.Disabled, QPalette.Highlight, mix("field", "muted", 0.35))
    return p


# ---------------------------------------------------------------------- assets

_ASSET_DIR = tempfile.mkdtemp(prefix="asterism-theme-")


def _asset(name: str, svg: str) -> str:
    path = os.path.join(_ASSET_DIR, f"{'dark' if is_dark() else 'light'}-{name}.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return path.replace(os.sep, "/")


def _assets() -> dict:
    t = tokens()
    stroke = "fill='none' stroke-linecap='round' stroke-linejoin='round'"
    svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' width='16' height='16'>{}</svg>"
    return {
        "check": _asset("check", svg.format(
            f"<path d='M4 8.4l2.6 2.6L12 5.4' {stroke} stroke='{t['on_accent']}' stroke-width='2'/>")),
        "dot": _asset("dot", svg.format(f"<circle cx='8' cy='8' r='3' fill='{t['on_accent']}'/>")),
        "chevron": _asset("chevron", svg.format(
            f"<path d='M4.5 6.5L8 10l3.5-3.5' {stroke} stroke='{t['muted']}' stroke-width='1.6'/>")),
        "branch_closed": _asset("branch-closed", svg.format(
            f"<path d='M6.5 4.5L10 8l-3.5 3.5' {stroke} stroke='{t['muted']}' stroke-width='1.5'/>")),
        "branch_open": _asset("branch-open", svg.format(
            f"<path d='M4.5 6.5L8 10l3.5-3.5' {stroke} stroke='{t['muted']}' stroke-width='1.5'/>")),
    }


# ------------------------------------------------------------------ stylesheet

def _qss() -> str:
    t, a = tokens(), _assets()
    c = {k: _css(v) for k, v in t.items()}
    c.update(
        hover=_alpha("text", 0.06), press=_alpha("text", 0.11), seg=_alpha("text", 0.08),
        accent_soft=_alpha("accent", 0.14), check_border=_alpha("text", 0.40),
        thumb=_alpha("muted", 0.35), thumb_hover=_alpha("muted", 0.55),
        sel=mix("field", "accent", 0.20).name(), grid=mix("field", "text", 0.13).name(),
        disabled=mix("chrome", "muted", 0.7).name(),
    )
    c.update({k: v for k, v in a.items()})
    return """
QMainWindow, QDialog {{ background: {chrome}; }}
QMainWindow::separator {{ background: {border}; width: 1px; height: 1px; }}
QSplitter::handle {{ background: {border}; }}
QToolTip {{ background: {surface}; color: {text}; border: 1px solid {control_border};
            border-radius: 5px; padding: 3px 6px; }}

/* Ribbon (toolbar) ----------------------------------------------------------- */
QToolBar#RibbonBar {{ background: {chrome}; border: none; border-bottom: 1px solid {border};
                      padding: 2px 0 3px 0; spacing: 0; }}
QLabel#RibbonCaption {{ color: {muted}; font-size: 11px; }}
QFrame#RibbonSep {{ background: {border}; border: none; }}
QLabel#Wordmark {{ color: {accent}; font-size: 15px; font-weight: 700; padding: 0 6px; }}
QToolButton {{ border: none; border-radius: 5px; background: transparent; color: {text};
               padding: 3px; }}
QToolButton:hover {{ background: {hover}; }}
QToolButton:pressed {{ background: {press}; }}
QToolButton:checked {{ background: {accent_soft}; color: {accent}; }}
QToolButton:disabled {{ color: {disabled}; }}
QToolButton[popupMode="1"] {{ padding-right: 13px; }}
QToolButton::menu-button {{ border: none; width: 12px; border-radius: 4px; }}
QToolButton::menu-arrow, QToolButton::menu-indicator {{ image: url({chevron}); width: 10px; height: 10px; }}

/* Project sidebar tree ------------------------------------------------------- */
QTreeWidget#NavTree {{ background: transparent; border: none; outline: 0;
                       show-decoration-selected: 0; }}
QTreeWidget#NavTree::item, QTreeWidget#NavTree::item:hover, QTreeWidget#NavTree::item:selected {{
    height: 24px; background: transparent; border: none; }}   /* NavDelegate paints rows */
QTreeWidget#NavTree::branch, QTreeWidget#NavTree::branch:selected,
QTreeWidget#NavTree::branch:hover {{ background: transparent; }}
QTreeWidget#NavTree::branch:has-children:closed {{ image: url({branch_closed}); }}
QTreeWidget#NavTree::branch:has-children:open {{ image: url({branch_open}); }}

/* Status bar ----------------------------------------------------------------- */
QStatusBar {{ background: {chrome}; border-top: 1px solid {border}; min-height: 26px; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {muted}; font-size: 11px; }}
QStatusBar QLineEdit {{ padding: 1px 6px; font-size: 12px; min-height: 16px; }}

/* Fields ---------------------------------------------------------------------- */
QLineEdit, QComboBox, QAbstractSpinBox, QPlainTextEdit, QTextEdit {{
    background: {field}; color: {text}; border: 1px solid {control_border}; border-radius: 5px;
    padding: 2px 7px; min-height: 18px; selection-background-color: {accent};
    selection-color: {on_accent}; }}
QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {accent}; }}
QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{ color: {disabled};
    background: {chrome}; }}
QAbstractSpinBox {{ padding-right: 7px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0; border: none; }}
QComboBox {{ padding-right: 22px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 20px;
                        border: none; }}
QComboBox::down-arrow {{ image: url({chevron}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {surface}; color: {text}; border: 1px solid {control_border};
    outline: 0; padding: 4px; selection-background-color: {accent}; selection-color: {on_accent}; }}

/* Buttons --------------------------------------------------------------------- */
QPushButton {{ background: {field}; color: {text}; border: 1px solid {control_border};
               border-radius: 6px; padding: 4px 14px; min-height: 16px; min-width: 52px; }}
QPushButton:hover {{ background: {surface_hover}; }}
QPushButton:pressed {{ background: {press}; }}
QPushButton:default {{ background: {accent}; border-color: {accent}; color: {on_accent}; }}
QPushButton:default:hover {{ background: {accent_hover}; border-color: {accent_hover}; }}
QPushButton:disabled {{ color: {disabled}; }}
QPushButton#ColorButton {{ padding: 0; min-width: 0; }}
QToolButton#HelpButton {{ background: {field}; border: 1px solid {control_border}; border-radius: 10px;
                          color: {muted}; font-weight: 600; padding: 0; }}
QToolButton#HelpButton:hover {{ background: {surface_hover}; }}

/* Checks ---------------------------------------------------------------------- */
QCheckBox, QRadioButton {{ spacing: 6px; color: {text}; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {disabled}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 13px; height: 13px; background: {field};
    border: 1px solid {check_border}; }}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 7px; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; image: url({check}); }}
QRadioButton::indicator:checked {{ background: {accent}; border-color: {accent}; image: url({dot}); }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ border-color: {control_border}; }}
QCheckBox::indicator:checked:disabled, QRadioButton::indicator:checked:disabled {{
    background: {accent_dim}; border-color: {accent_dim}; }}

/* Section titles and rules in dialogs ------------------------------------------ */
QLabel#SectionTitle, QCheckBox#SectionTitle {{ font-weight: 600; }}
QFrame#Rule {{ background: {border}; border: none; max-height: 1px; min-height: 1px; }}

/* Window structure (NED-Net's): project sidebar, top bar, tool panel, status strip ---- */
QWidget#ProjectSidebar {{ background: {sidebar}; }}
QLabel#Wordmark {{ color: {accent}; font-size: 15px; font-weight: 700; padding-left: 18px; }}
QLabel#SectionLabel {{ color: {muted}; font-size: 11px; font-weight: 600; }}
QToolButton#SectionAdd {{ color: {muted}; font-size: 15px; padding: 0 5px; border-radius: 4px; }}
QToolButton#SectionAdd:hover {{ background: {hover}; color: {accent}; }}
QWidget#TopBar {{ background: {chrome}; border-bottom: 1px solid {border}; }}
QLabel#SheetSubtitle {{ color: {muted}; font-size: 11px; }}
QLineEdit#SheetTitle {{ background: transparent; border: 1px solid transparent; padding: 0 3px;
                        font-size: 13px; font-weight: 600; min-height: 16px; }}
QLineEdit#SheetTitle:hover {{ border: 1px solid {control_border}; background: {field}; }}
QLineEdit#SheetTitle:focus {{ border: 1px solid {accent}; background: {field}; }}
QFrame#ToolSep {{ background: {border}; border: none; }}
QToolBar#TopTools {{ background: transparent; border: none; spacing: 2px; padding: 0; }}
QToolBar#TopTools::separator {{ background: {border}; width: 1px; margin: 9px 7px; }}
QToolBar#TopTools QToolButton {{ border-radius: 6px; padding: 5px; }}
QToolBar#TopTools QToolButton#qt_toolbar_ext_button {{ padding: 2px; }}
QToolButton#TopTool, QToolButton#Tool {{ border-radius: 6px; padding: 0; }}
QToolButton#ExportButton, QToolButton#WideTool {{ background: {field}; border: 1px solid {control_border};
    border-radius: 6px; padding: 3px 10px; font-weight: 500; }}
QToolButton#ExportButton:hover, QToolButton#WideTool:hover {{ background: {surface_hover}; }}
QToolButton#ExportButton:disabled, QToolButton#WideTool:disabled {{ color: {disabled}; background: {chrome}; }}
QToolButton#ExportButton::menu-indicator {{ image: none; width: 0; }}
QWidget#ToolPanel {{ background: {chrome}; }}
QLabel#ToolGroup {{ color: {muted}; font-size: 11px; font-weight: 600; }}
QFrame#ToolRule {{ background: {border}; border: none; }}
QWidget#StatusStrip {{ background: {chrome}; border-top: 1px solid {border}; }}
QWidget#StatusStrip QLabel {{ color: {muted}; font-size: 11px; }}
QWidget#ProjectSidebar {{ border-right: 1px solid {border}; }}
QWidget#ToolPanel {{ border-left: 1px solid {border}; }}
QSplitter#MainSplitter::handle {{ background: transparent; }}
QSplitter#MainSplitter::handle:hover {{ background: {accent_soft}; }}

/* Dialogs: section sidebar + page ------------------------------------------------ */
QWidget#DialogSidebar {{ background: {sidebar}; border-right: 1px solid {border}; }}
QListWidget#DialogSections {{ background: transparent; border: none; outline: 0; }}
QListWidget#DialogSections::item, QListWidget#DialogSections::item:selected {{ background: transparent; }}
QWidget#DialogPage {{ background: {surface}; }}
QWidget#DialogPage QScrollArea, QWidget#DialogPage QScrollArea > QWidget > QWidget {{ background: transparent; }}
QWidget#ToolPanel QScrollArea, QWidget#ToolPanel QScrollArea > QWidget > QWidget {{ background: transparent; }}
QLabel#PageTitle {{ font-size: 15px; font-weight: 600; }}

/* Tabs: segmented control over a rounded pane (SegmentedTabBar paints the tabs) ---- */
QTabWidget::tab-bar {{ alignment: center; }}
QTabWidget::pane {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; top: -12px; }}
QTabWidget#ResultsTabs::tab-bar {{ alignment: left; left: 10px; }}
QTabWidget#ResultsTabs::pane {{ background: {field}; border: none; border-top: 1px solid {border};
                                border-radius: 0; top: 0; }}

/* Tables, lists, headers ----------------------------------------------------- */
QTableView, QTableWidget {{ background: {field}; color: {text}; border: none; gridline-color: {grid};
    selection-background-color: {sel}; selection-color: {text}; }}
QHeaderView {{ background: {sidebar}; }}
QHeaderView::section {{ background: {sidebar}; color: {muted}; border: none;
    border-right: 1px solid {grid}; border-bottom: 1px solid {grid}; padding: 0 6px; font-size: 12px; }}
QTreeWidget, QListWidget, QTreeView, QListView {{ background: {field}; color: {text};
    border: 1px solid {control_border}; border-radius: 5px; outline: 0; }}
QTreeWidget::item, QListWidget::item {{ min-height: 20px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: {accent}; color: {on_accent}; }}
QTreeView::branch:has-children:closed {{ image: url({branch_closed}); }}
QTreeView::branch:has-children:open {{ image: url({branch_open}); }}
QAbstractItemView::indicator {{ width: 13px; height: 13px; background: {field};
    border: 1px solid {check_border}; border-radius: 3px; }}
QAbstractItemView::indicator:checked {{ background: {accent}; border-color: {accent}; image: url({check}); }}

/* Scroll bars: thin, translucent ---------------------------------------------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle {{ background: {thumb}; border-radius: 3px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {thumb_hover}; }}
QScrollBar::handle:vertical {{ min-height: 30px; }}
QScrollBar::handle:horizontal {{ min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Menus, sliders --------------------------------------------------------------- */
QMenu {{ background: {surface}; color: {text}; border: 1px solid {control_border}; border-radius: 6px;
         padding: 4px 0; }}
QMenu::item {{ padding: 5px 22px 5px 16px; background: transparent; }}
QMenu::item:selected {{ background: {accent}; color: {on_accent}; }}
QMenu::item:disabled {{ color: {disabled}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 0; }}
QSlider::groove:horizontal {{ height: 4px; background: {control_border}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {field}; border: 1px solid {control_border}; width: 12px;
                              height: 12px; margin: -5px 0; border-radius: 7px; }}
""".format(**c)


# ---------------------------------------------------------------------- install

def apply(app: QApplication) -> None:
    _state["dark"] = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    app.setPalette(_palette())
    app.setStyleSheet(_qss())
    notifier.changed.emit()


def install(app: QApplication | None = None) -> None:
    """Fusion + palette + stylesheet; re-applied when the system switches light/dark."""
    app = app or QApplication.instance()
    if app is None or _state["installed"]:
        return
    _state["installed"] = True
    app.setStyle("Fusion")
    app.styleHints().colorSchemeChanged.connect(lambda _s: apply(app))
    apply(app)


# ------------------------------------------------------------- segmented tabs

class SegmentedTabBar(QTabBar):
    """Tabs drawn as a segmented control (NED-Net's .segmented), centred on the pane edge."""

    H = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self._hover = -1

    def tabSizeHint(self, i: int) -> QSize:
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self.tabText(i).replace("&&", "&")) + 30, self.H)

    def minimumTabSizeHint(self, i: int) -> QSize:
        return self.tabSizeHint(i)

    def mouseMoveEvent(self, e):
        h = self.tabAt(e.position().toPoint())
        if h != self._hover:
            self._hover = h
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._hover = -1
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        n = self.count()
        if not n:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        whole = QRectF(self.tabRect(0).topLeft(), self.tabRect(n - 1).bottomRight()).adjusted(0.5, 0.5, 0.5, 0.5)
        bg = mix("chrome", "text", 0.08) if not is_dark() else mix("chrome", "text", 0.10)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(whole, 7, 7)
        cur = self.currentIndex()
        sep = mix(bg, "text", 0.16)
        for i in range(n):
            r = QRectF(self.tabRect(i))
            if i == cur:
                pill = r.adjusted(2, 2, -2, -2)
                p.setBrush(QColor(0, 0, 0, 40 if not is_dark() else 90))
                p.drawRoundedRect(pill.translated(0, 0.6), 5, 5)
                p.setBrush(color("field") if not is_dark() else mix("field", "text", 0.10))
                p.drawRoundedRect(pill, 5, 5)
            else:
                if i == self._hover:
                    p.setBrush(mix(bg, "text", 0.06))
                    p.drawRoundedRect(r.adjusted(2, 2, -2, -2), 5, 5)
                if i + 1 < n and i + 1 != cur and i != self._hover and i + 1 != self._hover:
                    p.setPen(QPen(sep, 1))
                    x = r.right() + 0.5
                    p.drawLine(int(x), int(r.top() + 6), int(x), int(r.bottom() - 5))
                    p.setPen(Qt.NoPen)
        f = QFont(self.font())
        for i in range(n):
            f.setWeight(QFont.DemiBold if i == cur else QFont.Normal)
            p.setFont(f)
            p.setPen(color("text") if self.isTabEnabled(i) else color("muted"))
            p.drawText(QRectF(self.tabRect(i)), Qt.AlignCenter, self.tabText(i).replace("&&", "&"))
        p.end()


class Tabs(QTabWidget):
    """QTabWidget with the segmented tab bar."""

    def __init__(self, parent=None, name: str | None = None):
        super().__init__(parent)
        self.setTabBar(SegmentedTabBar(self))
        if name:
            self.setObjectName(name)
