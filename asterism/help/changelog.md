# What's new in ASTERISM

<!--
Shown in the "What's new" window the first time a new version starts, and from
Help › What's New…. Newest version first.

- One `## <version>` heading per release, exactly as in asterism/__init__.py.
- Optional `### New`, `### Improved`, `### Fixed` groups.
- Short bullets written for users, not developers: a bold lead-in, one or two sentences.
- Link into the help with the help's own form: `[Read more](graphs.md#selecting-and-moving)`.
  tests/test_whats_new.py fails if a link doesn't land on a heading.
-->

## 0.3.0

### New

- **A full sample project.** **File › Open Sample Project** (and **Sample project** in the Start window) now opens a complete example to explore: every kind of data table, the main analyses, many graph types and a finished figure, all with made-up data. [Read more](start.md#the-start-window)
- **Resize a graph by dragging its axes.** Select an axis and drag the handles around the plot area. Hold Shift on a corner to keep the proportions. [Read more](graphs.md#selecting-and-moving)
- **This window.** Each new version now tells you what changed. [Read more](start.md#whats-new)

### Improved

- **Clearer selection on graphs.** A dotted outline shows what is selected, and handles appear only on things you can resize. [Read more](graphs.md#selecting-and-moving)

### Fixed

- **All graphs no longer widens the window.** Its filters wrap onto a second line in a narrow window, so the sidebars keep their room after you've visited it. [Read more](graphs.md#all-graphs-at-a-glance)
