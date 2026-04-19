"""Stress-test suite for :class:`MapParser`.

Run with: ``.venv/bin/python -m tests.test_parser``

Each case is a ``(label, map_text, expected)`` triple. ``expected`` is either
``None`` (the parse must succeed) or a substring that must appear in the
raised :class:`MapParseError` message.
"""

import os
import sys
import tempfile
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parser.parser import MapParser  # noqa: E402
from src.parser.errors import MapParseError  # noqa: E402


GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class Case:
    """One parser test case.

    Attributes:
        label: Human-readable test name.
        text: Map file contents (written to a temp file).
        expected: Error substring to match, or None for success.
    """

    label: str
    text: str
    expected: str | None


class ParserTester:
    """Runs a battery of parser cases and reports pass/fail counts."""

    def __init__(self) -> None:
        """Initialize the tester with its full case catalog."""
        self.cases: list[Case] = self._build_cases()

    def _build_cases(self) -> list[Case]:
        """Construct the catalog of happy-path and failure cases.

        Returns:
            A list of :class:`Case` objects covering every raise path
            in the parser plus representative happy paths.
        """
        base = (
            "nb_drones: 2\n"
            "start_hub: s 0 0\n"
            "end_hub: e 1 0\n"
            "connection: s-e\n"
        )
        return [
            # ---- Happy paths ----
            Case("happy: minimal valid", base, None),
            Case(
                "happy: with metadata",
                "nb_drones: 3\n"
                "start_hub: s 0 0 [color=green]\n"
                "hub: mid 1 0 [color=blue max_drones=2]\n"
                "end_hub: e 2 0 [color=red]\n"
                "connection: s-mid\n"
                "connection: mid-e [max_link_capacity=2]\n",
                None,
            ),
            Case(
                "happy: all zone types",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "hub: p 1 0 [zone=priority]\n"
                "hub: r 2 0 [zone=restricted]\n"
                "hub: n 3 0 [zone=normal]\n"
                "end_hub: e 4 0\n"
                "connection: s-p\n"
                "connection: p-r\n"
                "connection: r-n\n"
                "connection: n-e\n",
                None,
            ),
            Case(
                "happy: comments and blanks skipped",
                "# top comment\n"
                "\n"
                "nb_drones: 1\n"
                "   \n"
                "# another\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                None,
            ),
            Case(
                "happy: negative coords allowed",
                "nb_drones: 1\n"
                "start_hub: s -5 -3\n"
                "end_hub: e -1 -1\n"
                "connection: s-e\n",
                None,
            ),
            # ---- File-level ----
            # (handled separately in run() — path doesn't exist)

            # ---- nb_drones ----
            Case(
                "fail: missing nb_drones",
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "missing nb_drones",
            ),
            Case(
                "fail: duplicate nb_drones",
                "nb_drones: 1\n"
                "nb_drones: 2\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "duplicate nb_drones",
            ),
            Case(
                "fail: nb_drones not an integer",
                "nb_drones: abc\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "nb_drones must be an integer",
            ),
            Case(
                "fail: nb_drones zero",
                "nb_drones: 0\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "nb_drones must be >= 1",
            ),
            Case(
                "fail: nb_drones negative",
                "nb_drones: -5\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "nb_drones must be >= 1",
            ),
            # ---- Hubs ----
            Case(
                "fail: missing start_hub",
                "nb_drones: 1\n"
                "end_hub: e 1 0\n",
                "missing start_hub",
            ),
            Case(
                "fail: missing end_hub",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n",
                "missing end_hub",
            ),
            Case(
                "fail: duplicate start_hub",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "start_hub: s2 1 0\n"
                "end_hub: e 2 0\n"
                "connection: s-e\n",
                "duplicate start_hub",
            ),
            Case(
                "fail: duplicate end_hub",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "end_hub: e2 2 0\n"
                "connection: s-e\n",
                "duplicate end_hub",
            ),
            # ---- Zone parsing ----
            Case(
                "fail: zone mismatched brackets",
                "nb_drones: 1\n"
                "start_hub: s 0 0 [color=green\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "mismatched metadata brackets",
            ),
            Case(
                "fail: zone missing coords",
                "nb_drones: 1\n"
                "start_hub: s 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "expected 'name x y'",
            ),
            Case(
                "fail: zone too many tokens",
                "nb_drones: 1\n"
                "start_hub: s 0 0 extra\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "expected 'name x y'",
            ),
            Case(
                "fail: zone name contains dash",
                "nb_drones: 1\n"
                "start_hub: bad-name 0 0\n"
                "end_hub: e 1 0\n"
                "connection: bad-name-e\n",
                "must not contain '-'",
            ),
            Case(
                "fail: duplicate zone name",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "hub: s 1 0\n"
                "end_hub: e 2 0\n"
                "connection: s-e\n",
                "duplicate zone name",
            ),
            Case(
                "fail: zone x not integer",
                "nb_drones: 1\n"
                "start_hub: s abc 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "x must be an integer",
            ),
            Case(
                "fail: zone y not integer",
                "nb_drones: 1\n"
                "start_hub: s 0 abc\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "y must be an integer",
            ),
            Case(
                "fail: max_drones not integer",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "hub: h 1 0 [max_drones=abc]\n"
                "end_hub: e 2 0\n"
                "connection: s-h\n"
                "connection: h-e\n",
                "max_drones must be an integer",
            ),
            Case(
                "fail: max_drones zero",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "hub: h 1 0 [max_drones=0]\n"
                "end_hub: e 2 0\n"
                "connection: s-h\n"
                "connection: h-e\n",
                "max_drones must be >= 1",
            ),
            Case(
                "fail: invalid zone_type",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "hub: h 1 0 [zone=weird]\n"
                "end_hub: e 2 0\n"
                "connection: s-h\n"
                "connection: h-e\n",
                "not a valid zone type",
            ),
            # ---- Connection parsing ----
            Case(
                "fail: connection mismatched brackets",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e [max_link_capacity=1\n",
                "mismatched metadata brackets",
            ),
            Case(
                "fail: connection body no dash",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: se\n",
                "expected 'zone_a-zone_b'",
            ),
            Case(
                "fail: connection body too many dashes",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e-x\n",
                "expected 'zone_a-zone_b'",
            ),
            Case(
                "fail: self-loop",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-s\n",
                "self-loop",
            ),
            Case(
                "fail: unknown zone a",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: ghost-e\n",
                "unknown zone 'ghost'",
            ),
            Case(
                "fail: unknown zone b",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-ghost\n",
                "unknown zone 'ghost'",
            ),
            Case(
                "fail: duplicate connection same order",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n"
                "connection: s-e\n",
                "duplicate connection",
            ),
            Case(
                "fail: duplicate connection reverse order",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n"
                "connection: e-s\n",
                "duplicate connection",
            ),
            Case(
                "fail: max_link_capacity zero",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e [max_link_capacity=0]\n",
                "max_link_capacity must be >= 1",
            ),
            Case(
                "fail: max_link_capacity not integer",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e [max_link_capacity=abc]\n",
                "max_link_capacity must be an integer",
            ),
            # ---- Metadata ----
            Case(
                "fail: metadata token no equals",
                "nb_drones: 1\n"
                "start_hub: s 0 0 [color]\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "expected key=value",
            ),
            Case(
                "fail: metadata empty key",
                "nb_drones: 1\n"
                "start_hub: s 0 0 [=green]\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "empty metadata key or value",
            ),
            Case(
                "fail: metadata empty value",
                "nb_drones: 1\n"
                "start_hub: s 0 0 [color=]\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n",
                "empty metadata key or value",
            ),
            # ---- Unknown directive ----
            Case(
                "fail: unknown directive",
                "nb_drones: 1\n"
                "start_hub: s 0 0\n"
                "end_hub: e 1 0\n"
                "connection: s-e\n"
                "weirdo: foo\n",
                "unknown directive 'weirdo'",
            ),
        ]

    def _run_case(self, case: Case) -> tuple[bool, str]:
        """Execute a single case against a temp-file-backed parser.

        Args:
            case: The :class:`Case` to run.
        Returns:
            A tuple ``(passed, detail)`` where ``detail`` is either an
            empty string on pass or a short failure explanation.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write(case.text)
            path = f.name
        try:
            try:
                MapParser(path).parse()
                got_error: MapParseError | None = None
            except MapParseError as e:
                got_error = e
            if case.expected is None:
                if got_error is None:
                    return True, ""
                return False, f"expected success, raised: {got_error}"
            if got_error is None:
                return False, f"expected error '{case.expected}', got success"
            if case.expected not in str(got_error):
                return False, (
                    f"expected substring '{case.expected}' in error, "
                    f"got: {got_error}"
                )
            return True, ""
        finally:
            os.unlink(path)

    def _run_file_error(self) -> tuple[str, bool, str]:
        """Test the missing-file branch without a temp file.

        Returns:
            A ``(label, passed, detail)`` triple mirroring ``_run_case``.
        """
        label = "fail: file does not exist"
        try:
            MapParser("/nonexistent/path/to/map.txt").parse()
            return label, False, "expected error, got success"
        except MapParseError as e:
            if "cannot read map" in str(e):
                return label, True, ""
            return label, False, f"got wrong message: {e}"

    def run(self) -> int:
        """Run every case and print a summary.

        Returns:
            0 if all cases passed, 1 otherwise.
        """
        passed = 0
        failed: list[tuple[str, str]] = []
        print(f"{BOLD}Running parser test suite{RESET}")
        print(f"{DIM}{'-' * 60}{RESET}")
        for case in self.cases:
            ok, detail = self._run_case(case)
            if ok:
                passed += 1
                print(f"  {GREEN}PASS{RESET}  {case.label}")
            else:
                failed.append((case.label, detail))
                print(f"  {RED}FAIL{RESET}  {case.label}")
                print(f"        {DIM}{detail}{RESET}")
        label, ok, detail = self._run_file_error()
        if ok:
            passed += 1
            print(f"  {GREEN}PASS{RESET}  {label}")
        else:
            failed.append((label, detail))
            print(f"  {RED}FAIL{RESET}  {label}")
            print(f"        {DIM}{detail}{RESET}")
        total = len(self.cases) + 1
        print(f"{DIM}{'-' * 60}{RESET}")
        if failed:
            print(
                f"{RED}{BOLD}{passed}/{total} passed, "
                f"{len(failed)} failed{RESET}"
            )
            return 1
        print(f"{GREEN}{BOLD}All {total} tests passed{RESET}")
        return 0


if __name__ == "__main__":
    sys.exit(ParserTester().run())
