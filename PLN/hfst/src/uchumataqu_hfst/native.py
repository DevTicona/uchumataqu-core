"""Ejecución de HFST instalado localmente, sin modificar el entorno del sistema."""
import os
import subprocess

from .data import ROOT


def run(tool, *args, text=None):
    prefix = ROOT / 'tools/root/usr'
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(prefix / 'lib/x86_64-linux-gnu') + (
        ':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    result = subprocess.run([str(prefix / 'bin' / tool), *map(str, args)],
                            input=text, capture_output=True, encoding='utf-8',
                            env=env, timeout=60, check=True)
    return result.stdout


def lookup(model, inputs):
    if not inputs:
        return {}
    if any('\n' in value or '\r' in value or '\t' in value for value in inputs):
        raise ValueError('Una consulta debe ocupar una sola línea.')
    model_str = str(model)
    results = {value: set() for value in inputs}
    if model_str.endswith('.hfstol'):
        output = run('hfst-optimized-lookup', '-q', model,
                     text='\n'.join(inputs) + '\n')
        for line in output.splitlines():
            columns = line.split('\t')
            if len(columns) == 2 and columns[0] in results:
                val = columns[1].strip()
                if val and not val.endswith('+?'):
                    results[columns[0]].add(val)
            elif len(columns) >= 3 and columns[0] in results:
                if columns[2].strip() not in {'+?', 'inf', 'infinity'}:
                    val = columns[1].strip()
                    if val and not val.endswith('+?'):
                        results[columns[0]].add(val)
    else:
        output = run('hfst-lookup', '--quiet', '--pipe-mode=input', model,
                     text='\n'.join(inputs) + '\n')
        for line in output.splitlines():
            columns = line.split('\t')
            if len(columns) >= 3 and columns[0] in results and columns[2] not in {'+?', 'inf', 'infinity'}:
                val = columns[1].strip()
                if val and not val.endswith('+?'):
                    results[columns[0]].add(val)
    return results
