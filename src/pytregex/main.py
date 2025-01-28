#!/usr/bin/env python3

import argparse
import contextlib
import glob
import logging
import os
import sys

from .tregex import TregexPattern
from .utils import TregexProcedureResult


class TregexUI:
    def __init__(self) -> None:
        self.args_parser: argparse.ArgumentParser = self.create_args_parser()

    def __add_log_levels(self, parser: argparse.ArgumentParser) -> None:
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--quiet",
            dest="is_quiet",
            action="store_true",
            default=False,
            help="disable all loggings",
        )
        group.add_argument(
            "--verbose",
            dest="is_verbose",
            action="store_true",
            default=False,
            help="enable verbose loggings",
        )

    def create_args_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="pytregex", formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument(
            "--version",
            action="store_true",
            default=False,
            help="show version and exit",
        )
        self.__add_log_levels(parser)
        subparsers: argparse._SubParsersAction = parser.add_subparsers(title="commands", dest="command")
        self.pattern_parser = self.create_pattern_parser(subparsers)
        self.explain_parser = self.create_explain_parser(subparsers)
        self.pprint_parser = self.create_pprint_parser(subparsers)
        return parser

    def create_pattern_parser(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        pattern_parser = subparsers.add_parser(
            "pattern", help="match tregex pattern against constituency trees", add_help=False
        )

        pattern_parser.add_argument("pattern", nargs="?", help="Tregex pattern")
        pattern_parser.add_argument(
            "--help",
            action="help",
            help="show this message and exit.",
        )
        pattern_parser.add_argument(
            "-filter",
            action="store_true",
            dest="is_stdin",
            default=False,
            help="read tree input from stdin.",
        )
        pattern_parser.add_argument(
            "-C",
            action="store_true",
            dest="is_count",
            default=False,
            help="suppress printing of matches, so only the number of matches is printed.",
        )
        pattern_parser.add_argument(
            "-h",
            metavar="<handle>",
            action="extend",
            nargs="+",
            dest="handles",
            help=(
                "for each node-handle specified, the node matched and given that handle will be"
                " printed. Multiple nodes can be printed by using this option multiple times on"
                " a single command line."
            ),
        )
        pattern_parser.add_argument(
            "--version",
            action="store_true",
            default=False,
            help="show version and exit.",
        )

        self.__add_log_levels(pattern_parser)
        pattern_parser.set_defaults(func=self.run_pattern_args)
        return pattern_parser

    def create_explain_parser(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        explain_parser = subparsers.add_parser("explain", help="explain the given relation operator")
        explain_parser.add_argument("relop", nargs="?", help="relation operator to explain")
        self.__add_log_levels(explain_parser)
        explain_parser.set_defaults(func=self.run_explain_args)
        return explain_parser

    def create_pprint_parser(self, subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        pprint_parser = subparsers.add_parser("pprint", help="pretty print the give constituency tree")
        group = pprint_parser.add_mutually_exclusive_group()
        group.add_argument("treestring", nargs="?", help="the constituency tree to print")
        group.add_argument(
            "-",
            action="store_true",
            dest="is_stdin",
            default=False,
            help="Read tree input from stdin",
        )
        self.__add_log_levels(pprint_parser)
        pprint_parser.set_defaults(func=self.run_pprint_args)
        return pprint_parser

    def run_pattern_args(self, options: argparse.Namespace) -> TregexProcedureResult:
        if options.pattern is None:
            self.pattern_parser.print_help()
            return True, None

        self.tree_string = None
        self.verified_ifile_list = None
        if options.is_stdin:
            if self.ipath_list:
                return (
                    False,
                    "Input files are unaccepted when reading tree input from stdin: \n\n{}".format(
                        "\n".join(self.ipath_list)
                    ),
                )
            self.tree_string = sys.stdin.read()
        else:
            verified_ifile_list = []
            for path in self.ipath_list:
                if os.path.isfile(path):
                    verified_ifile_list.append(path)
                elif os.path.isdir(path):
                    verified_ifile_list.extend(glob.glob(f"{path}{os.path.sep}*.txt"))
                elif glob.glob(path):
                    verified_ifile_list.extend(glob.glob(path))
                else:
                    return (False, f"No such file as \n\n{path}")
            if verified_ifile_list:
                self.verified_ifile_list = verified_ifile_list

        default_tree_string = (
            "(VP (VP (VBZ Try) (NP (NP (DT this) (NN wine)) (CC and) (NP (DT these) (NNS snails)))) (PUNCT .))"
        )

        # run matcher
        if self.verified_ifile_list is not None:
            forests = []
            for ifile in self.verified_ifile_list:
                logging.debug(f"Reading tree input from input {ifile}...")
                with open(ifile, encoding="utf-8") as f:
                    forests.append(f.read())
            tree_string = "\n".join(forests)
        elif self.tree_string is not None:
            logging.debug("Reading tree input from stdin...")
            tree_string = self.tree_string
        else:
            logging.debug(f"No tree input. Using the default {default_tree_string}.")
            tree_string = default_tree_string

        # from viztracer import VizTracer
        # tracer = VizTracer()
        # tracer.start()
        pattern = TregexPattern(options.pattern)
        matches = pattern.findall(tree_string)
        # tracer.stop()
        # tracer.save()

        if options.handles:
            logging.debug("Printing handles...")
            for handle in options.handles:
                handled_nodes = pattern.get_nodes(handle)
                for node in handled_nodes:
                    with contextlib.suppress(BrokenPipeError):
                        sys.stdout.write(f"{node}\n")
        else:
            if options.is_count:
                with contextlib.suppress(BrokenPipeError):
                    sys.stdout.write(f"{len(matches)}\n")
                return True, None
            logging.debug("Printing matches...")
            for m in matches:
                with contextlib.suppress(BrokenPipeError):
                    sys.stdout.write(f"{m}\n")
        logging.info(f"There were {len(matches)} matches in total.")

        return True, None

    def run_explain_args(self, options: argparse.Namespace) -> TregexProcedureResult:
        if options.relop is None:
            self.explain_parser.print_help()
            return True, None

        from .glossary import explain

        with contextlib.suppress(BrokenPipeError):
            if (ret := explain(options.relop)) is not None:
                sys.stdout.write(f"{ret}\n")
        return True, None

    def run_pprint_args(self, options: argparse.Namespace) -> TregexProcedureResult:
        if options.treestring is None and not options.is_stdin:
            self.pprint_parser.print_help()
            return True, None

        from .tree import Tree

        for t in Tree.fromstring(options.treestring or sys.stdin.read()):
            with contextlib.suppress(BrokenPipeError):
                sys.stdout.write(f"{t.render()}\n")
        return True, None

    def run_args(self, argv: list[str]) -> TregexProcedureResult:
        options, self.ipath_list = self.args_parser.parse_known_args(argv[1:])

        if options.version:
            return self.show_version()

        if options.is_quiet:
            logging.basicConfig(format="%(message)s", level=logging.CRITICAL)
        elif options.is_verbose:
            logging.basicConfig(format="%(message)s", level=logging.DEBUG)
        else:
            logging.basicConfig(format="%(message)s", level=logging.INFO)

        if (func := getattr(options, "func", None)) is not None:
            return func(options)

        self.args_parser.print_help()
        return True, None

    def show_version(self) -> TregexProcedureResult:
        from about import __version__

        print(__version__)
        return True, None


def main() -> None:
    ui = TregexUI()
    success, err_msg = ui.run_args(sys.argv)
    if not success:
        logging.critical(err_msg)
        sys.exit(1)
