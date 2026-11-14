#!/usr/bin/env python3
"""Start de gesprekstool. Zonder argumenten opent het venster; met argumenten de opdrachtregel."""
import sys


def main():
    if len(sys.argv) > 1:
        from gesprekstool import cli
        sys.exit(cli.main())
    from gesprekstool import venster
    venster.main()


if __name__ == "__main__":
    main()
