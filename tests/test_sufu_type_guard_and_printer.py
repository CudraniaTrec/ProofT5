import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from SuFu.sufu_model import (
    TermApp,
    TermUnlabel,
    TermVar,
    TypeCtx,
    parser,
    visit,
)
from beamsearch_sufu import SearchNode
from beamsearch_sufu import finishsetBm


def parse_program(code):
    tree = parser.parse(code.encode("utf-8"))
    if tree.root_node.has_error:
        raise AssertionError(tree.root_node.sexp())
    return visit(tree.root_node, {"code": code})


class SufuTypeGuardAndPrinterTests(unittest.TestCase):
    def test_tree_sitter_ast_is_marked_complete_and_type_checked(self):
        node = parse_program("x = 1;\nmain = x;")
        context = node.type_check(TypeCtx())
        self.assertIn("x", context.ctx)
        self.assertIn("main", context.ctx)

    def test_tree_sitter_type_check_rejects_unbound_variable(self):
        node = parse_program("main = missing;")
        with self.assertRaisesRegex(AssertionError, "missing not in ctx"):
            node.type_check(TypeCtx())

    def test_completed_beam_guard_rejects_unbound_variable(self):
        search_node = SearchNode.__new__(SearchNode)
        search_node.node = parse_program("main = missing;")
        search_node.isfinish = True
        search_node.terms_need = []
        self.assertFalse(search_node.is_type_correct())

    def test_final_write_guard_rejects_invalid_rendered_program(self):
        class InternallyAcceptedButBadSurface:
            isfinish = True
            prob = -1.0
            state = [0]

            def is_surface_type_correct(self):
                return False

            def to_str(self):
                return "main = missing;"

        candidates = finishsetBm(1)
        candidates.add(InternallyAcceptedButBadSurface())
        candidates.finalize()
        self.assertEqual(candidates.final_set, [])

    def test_surface_guard_accepts_valid_program(self):
        search_node = SearchNode.__new__(SearchNode)
        search_node.node = parse_program("x = 1;\nmain = x;")
        search_node.isfinish = True
        search_node.terms_need = []
        self.assertTrue(search_node.is_surface_type_correct())

    def test_surface_guard_rejects_unbound_rendered_program(self):
        search_node = SearchNode.__new__(SearchNode)
        search_node.node = parse_program("main = missing;")
        search_node.isfinish = True
        search_node.terms_need = []
        self.assertFalse(search_node.is_surface_type_correct())

    def test_application_printer_preserves_prefix_argument_grouping(self):
        node = TermApp(TermVar("sort"), TermUnlabel(TermVar("tmp")))
        self.assertEqual(node.to_str({}), "sort (unlabel tmp)")


if __name__ == "__main__":
    unittest.main()
