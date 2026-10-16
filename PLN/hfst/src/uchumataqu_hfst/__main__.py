import argparse
import json
import subprocess

from .build import build
from .runtime import Analyzer


def main():
    parser = argparse.ArgumentParser(description='HFST uchumataqu: formas documentadas')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('build')
    analyze = commands.add_parser('analyze')
    analyze.add_argument('text')
    compare = commands.add_parser('compare')
    compare.add_argument('target')
    compare.add_argument('response')
    args = parser.parse_args()
    try:
        if args.command == 'build':
            result = build()
        elif args.command == 'analyze':
            result = Analyzer().analyze(args.text)
        else:
            result = Analyzer().compare(args.target, args.response)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'technical_error', 'detail': str(error)}, ensure_ascii=False))
        raise SystemExit(1) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
