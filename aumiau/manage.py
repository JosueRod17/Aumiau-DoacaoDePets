#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
from pathlib import Path
import subprocess
import sys


def usar_ambiente_local():
    """Um Python global usa a .venv existente; ambientes explícitos são respeitados."""
    if sys.prefix != sys.base_prefix or hasattr(sys, 'real_prefix'):
        return
    raiz = Path(__file__).resolve().parent.parent
    ambiente = raiz / '.venv'
    executavel = ambiente / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not executavel.is_file() or not (ambiente / 'pyvenv.cfg').is_file():
        return
    contexto = os.environ.copy()
    contexto.pop('PYTHONHOME', None)
    contexto['VIRTUAL_ENV'] = str(ambiente)
    contexto['PATH'] = str(executavel.parent) + os.pathsep + contexto.get('PATH', '')
    try:
        resultado = subprocess.call(
            [str(executavel), str(Path(__file__).resolve()), *sys.argv[1:]],
            env=contexto,
        )
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    raise SystemExit(resultado)


def main():
    """Run administrative tasks."""
    usar_ambiente_local()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aumiau.settings')
    try:
        from django.core.management import execute_from_command_line
    except ModuleNotFoundError as exc:
        if exc.name != 'django':
            raise
        raise SystemExit(
            f'O Python em uso não tem Django: {sys.executable}\n'
            'Na raiz do projeto, crie a .venv e instale requirements.txt.\n'
            'Se outro ambiente estiver ativo, desative-o ou selecione a .venv deste projeto.'
        ) from None
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
