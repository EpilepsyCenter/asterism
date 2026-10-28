"""Entry point for the packaged app (PyInstaller)."""

import multiprocessing
import sys

from asterism.app.main import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
