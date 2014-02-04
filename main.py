#!/usr/bin/python

"""
Entry point of the application
"""

import sys
import editorGUI


def main(argv):
    editorApp = editorGUI.application()
    sys.exit(editorApp.run())


if __name__ == "__main__":
    main(sys.argv[1:])

