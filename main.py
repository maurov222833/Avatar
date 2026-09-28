import os
import sys

# Asegurar que el directorio raíz del proyecto esté en el PYTHONPATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from interface.cli import run_cli

if __name__ == "__main__":
    run_cli()
