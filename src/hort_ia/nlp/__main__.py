"""`python -m hort_ia.nlp "quando planto alface?"`: what the assistant understands of a message.

Without a message, reads one per line from the standard input. Prints the interpretation as JSON.
"""

import sys

from .nlu import get_interpreter


def main() -> None:
    messages = sys.argv[1:] or [line.strip() for line in sys.stdin if line.strip()]
    interpreter = get_interpreter()
    for message in messages:
        print(f"> {message}")
        print(interpreter.interpret(message).model_dump_json(indent=2, exclude_defaults=True))


main()
