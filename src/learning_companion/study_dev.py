"""Development-only command: run one question through the study-helper chain.

Usage: uv run python -m learning_companion.study_dev "What is an API?"
"""

import sys

from learning_companion.chain import ConfigurationError, build_study_helper_chain
from learning_companion.config import get_settings


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Usage: python -m learning_companion.study_dev "your question"')
        return 2
    question = sys.argv[1]
    try:
        chain = build_study_helper_chain(get_settings())
    except ConfigurationError as error:
        print(error)
        return 1
    print(chain.invoke({"history": [], "question": question}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
