import argparse
import asyncio
import logging
import sys

from dishka import make_async_container

from app.config.logging import configure_logging
from app.di.providers import PROVIDERS
from app.domain.errors import KantKodError
from app.domain.use_cases.validate_json import ValidateJsonUseCase

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app", description="KantKod command line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate",
        help="Analyze a local JSON payload without calling the source portal",
    )
    validate.add_argument("--input", required=True, help="Path to a local JSON file in the source API format")
    validate.add_argument("--output", required=True, help="Path for the resulting report JSON")
    return parser


async def run_validate(input_path: str, output_path: str) -> int:
    container = make_async_container(*PROVIDERS)
    try:
        async with container() as scope:
            use_case = await scope.get(ValidateJsonUseCase)
            result = await use_case.execute(input_path=input_path, output_path=output_path)
    finally:
        await container.close()

    print(f"Report written to {result.report_path}")
    print(f"Vacancies: {result.vacancies_count}, issues: {result.issues_count}")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging("INFO")
    args = build_parser().parse_args(argv)

    try:
        if args.command == "validate":
            return asyncio.run(run_validate(args.input, args.output))
    except KantKodError as exc:
        logger.error("command failed", extra={"error": f"{type(exc).__name__}: {exc}"})
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
