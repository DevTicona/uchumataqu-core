import argparse
import json
from pathlib import Path

from .data import ROOT, prepare, read


def main():
    parser = argparse.ArgumentParser(description='Piloto Seq2Seq uchumataqu')
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/pilot.json')
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'smoke', 'train', 'export'):
        commands.add_parser(command)
    analyze = commands.add_parser('analyze')
    analyze.add_argument('text')
    args = parser.parse_args()
    try:
        config = read(args.config)
        if args.command == 'prepare':
            prepare(config)
            result = read(ROOT / 'reports/data-audit.json')
        elif args.command == 'analyze':
            from .runtime import Analyzer
            result = Analyzer().analyze(args.text)
        else:
            dataset = read(ROOT / 'data/prepared/dataset.json')
            if args.command == 'train':
                from .training import train
                if not (ROOT / 'runs/export-smoke/parity.json').exists():
                    raise ValueError('Ejecutar smoke antes del entrenamiento.')
                if config['annotation_policy'] != 'exploratory_unreviewed_not_gold':
                    raise ValueError('Los datos disponibles solo autorizan un piloto exploratorio.')
                result = train(dataset, config)
            else:
                from .exporting import export, smoke
                result = smoke(dataset, config) if args.command == 'smoke' else export(dataset)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, RuntimeError) as error:
        print(json.dumps({'status': 'technical_error', 'detail': str(error)}, ensure_ascii=False))
        raise SystemExit(1) from error


if __name__ == '__main__':
    main()
