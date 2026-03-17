import logging
import sys

from .generate import main

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
main()
