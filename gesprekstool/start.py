#!/usr/bin/env python3
"""Start de gesprekstool. Zonder argumenten opent het venster; met argumenten de opdrachtregel."""
import sys


def main():
    # Oudere macOS-versies geven een app bij het starten een "-psn_..."-argument mee.
    sys.argv = [a for a in sys.argv if not a.startswith("-psn")]
    if len(sys.argv) > 1:
        from gesprekstool import cli
        sys.exit(cli.main())
    from gesprekstool import venster
    venster.main()


if __name__ == "__main__":
    main()
