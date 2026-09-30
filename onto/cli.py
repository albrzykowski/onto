"""The `onto` command: build and update an ontology without writing code."""

import argparse
import logging
import sys
from pathlib import Path

from onto.builder import BuildError, build
from onto.config import (
    BuilderConfig,
    ConfigValidationError,
    MissingAPIKeyError,
    load_config,
)
from onto.dedup import Embedder, EmbeddingError
from onto.llm import LLM, LLMError

logger = logging.getLogger(__name__)

PROG = "onto"

BUILD = "build"
UPDATE = "update"

# what a command means for the build, which names its modes after what they do to the output
# rather than after the command: `build` starts the ontology over, `update` leaves what is
# there and extends it
COMMAND_MODES = {BUILD: "override", UPDATE: "update"}

EPILOG = """\
The configuration file names the provider, the model and the key the build runs with:

  onto build --config config.yaml --input corpus/ --output ontology/
  onto update --config config.yaml --input more/ --output ontology/
"""


def llm_for(config: BuilderConfig) -> LLM:
    """The chat adapter of the configured provider, imported only where it is used: a build
    naming one provider must not fail because the SDK of the other one is absent."""
    from onto.llm_litellm import LiteLLMLLM

    return LiteLLMLLM(api_key=config.api_key, provider=config.provider)


def embedder_for(config: BuilderConfig) -> Embedder:
    """Update mode needs embeddings, and it takes them from the provider that answers the
    prompts, so a build needs one key and one account rather than two."""
    from onto.embeddings import EMBEDDING_MODELS, LiteLLMEmbedder

    return LiteLLMEmbedder(api_key=config.api_key, model=EMBEDDING_MODELS[config.provider])


def _add_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--config", default="config.yaml", help="path to the YAML configuration"
    )
    command.add_argument("--input", required=True, help="directory of documents to read")
    command.add_argument("--output", required=True, help="directory to write the ontology to")


def parser() -> argparse.ArgumentParser:
    """The command-line interface of the library."""
    root = argparse.ArgumentParser(
        prog=PROG,
        description="Build and update LinkML ontologies from documents, with an LLM.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = root.add_subparsers(dest="command", metavar="{build,update}", required=True)
    _add_arguments(commands.add_parser(BUILD, help="build the ontology from scratch"))
    _add_arguments(
        commands.add_parser(UPDATE, help="extend an ontology already in the output directory")
    )
    return root


def main(argv: list[str] | None = None) -> int:
    """Run one command and return the exit code the shell should report."""
    arguments = parser().parse_args(argv)
    # the build reports what it skipped and what it wrote, and the provider SDKs log every
    # request they make, which would bury both
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        return _run(arguments)
    except (
        BuildError,
        ConfigValidationError,
        EmbeddingError,
        LLMError,
        MissingAPIKeyError,
        OSError,
    ) as error:
        # a user who mistyped a path or left out a key is told what went wrong, not shown the
        # library's stack: the trace is for a defect, and these are the errors a command makes
        print(f"onto: {error}", file=sys.stderr)
        return 1


def _load(path: str) -> BuilderConfig:
    """Read the configuration, naming the file a reader cannot open: a bare errno says which
    system call failed, not which of the paths a user typed was wrong."""
    try:
        return load_config(path)
    except OSError as error:
        raise ConfigValidationError(f"cannot read the configuration {path}: {error}") from error


def _run(arguments: argparse.Namespace) -> int:
    config = _load(arguments.config)
    mode = COMMAND_MODES[arguments.command]
    if config.mode != mode:
        # the command a user types is what decides: a `build` that quietly extended an earlier
        # ontology, or an `update` that discarded it, would be a surprise with no warning
        logger.warning(
            "%s runs in %s mode, so mode %r from the configuration is ignored",
            arguments.command,
            mode,
            config.mode,
        )
    build(
        input_dir=Path(arguments.input),
        output_dir=Path(arguments.output),
        config=config.model_copy(update={"mode": mode}),
        llm=llm_for(config),
        embedder=embedder_for(config) if mode == UPDATE else None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
