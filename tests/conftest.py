"""
Aislamiento cuando el runner es pytest.

``unittest discover`` no importa este archivo. El mismo pin corre desde
``core/__init__.py`` en cuanto la suite importa ``core``, que es el camino
de ``python -m unittest discover``.
"""
from core.test_home import pin_test_home

pin_test_home()
