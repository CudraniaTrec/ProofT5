#!/usr/bin/env python3
"""Build deterministic, interpreter-checked SuFu tasks with the frozen vocabulary."""

import argparse
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "SuFu"))

import sufu_model  # noqa: E402


DEFAULT_REFERENCE_TASK = (
    "sufucoq_t5gemma2_2b_retok_promptprefix_corrected_from_java30_20260715"
)
COMMON_CASES = [
    [],
    [1],
    [-1],
    [0, 1, -2, 3],
    [5, -5, 2],
    [2, 2, 2],
    [-3, -2, -1],
    [10, 0, -10, 4],
    [1, -1, 1, -1],
    [4, 3, 2, 1],
]
LIST_DECL = "Inductive List = cons {Int, List} | nil Unit;\n"
INT_WRAPPER = r"""
single_pass = \v: List -> Int.
    let run = (fix (
    \f: List -> Compress List. \xs: List.
    match xs with
      nil _ -> align (label xs)
    | cons {h, t} ->
        let tail = (f t) in
            align (label (cons {h, unlabel tail}))
    end
)) in
        \xs: List.
        let copied = (run xs) in
            align (v (unlabel copied));
"""
BOOL_WRAPPER = r"""
single_pass_bool = \v: List -> Bool.
    let run = (fix (
    \f: List -> Compress List. \xs: List.
    match xs with
      nil _ -> align (label xs)
    | cons {h, t} ->
        let tail = (f t) in
            align (label (cons {h, unlabel tail}))
    end
)) in
        \xs: List.
        let copied = (run xs) in
            align (v (unlabel copied));
"""
TREE_DECL = "Inductive Tree = empty Unit | node {Int, Tree, Tree};\n"
TREE_INT_WRAPPER = r"""
tree_pass = \v: Tree -> Int.
    let run = (fix (
    \f: Tree -> Compress Tree. \t: Tree.
    match t with
      empty _ -> align (label t)
    | node {w, l, r} ->
        let left = (f l) in
            let right = (f r) in
                align (label (node {w, unlabel left, unlabel right}))
    end
)) in
        \t: Tree.
        let copied = (run t) in
            align (v (unlabel copied));
"""
TREE_BOOL_WRAPPER = TREE_INT_WRAPPER.replace(
    "Tree -> Int", "Tree -> Bool"
).replace("tree_pass =", "tree_pass_bool =")
PAIR_INT_WRAPPER = r"""
pair_pass = \v: List -> List -> Int.
    let copy = (fix (
    \f: List -> Compress List. \xs: List.
    match xs with
      nil _ -> align (label xs)
    | cons {h, t} ->
        let tail = (f t) in
            align (label (cons {h, unlabel tail}))
    end
)) in
        \a: List. \b: List.
        let left = (copy a) in
            let right = (copy b) in
                align (v (unlabel left) (unlabel right));
"""
PAIR_BOOL_WRAPPER = PAIR_INT_WRAPPER.replace(
    "List -> List -> Int", "List -> List -> Bool"
).replace("pair_pass =", "pair_pass_bool =")


def load_pickle(path):
    with Path(path).open("rb") as f:
        return pickle.load(f)


def dump_pickle(value, path):
    with Path(path).open("wb") as f:
        pickle.dump(value, f)


def dump_json(value, path):
    with Path(path).open("w") as f:
        json.dump(value, f, indent=2)


def integer(value):
    return str(value) if value >= 0 else f"({value})"


def list_literal(values):
    result = "(nil unit)"
    for value in reversed(values):
        result = f"(cons {{{integer(value)}, {result}}})"
    return result


def task(name, description, task_code, oracle, result_type="Int"):
    wrapper = INT_WRAPPER if result_type == "Int" else BOOL_WRAPPER
    library = f"{LIST_DECL}{wrapper.strip()}\n"
    return {
        "file_name": f"synthetic-list-{name}",
        "desc": description,
        "lib_code": library,
        "task_code": task_code.strip() + "\n",
        "oracle": oracle,
        "result_type": result_type,
    }


def structural_task(
    name,
    description,
    library,
    task_code,
    cases,
    render_test,
    oracle,
    result_type="Int",
):
    return {
        "file_name": name,
        "desc": description,
        "lib_code": library.strip() + "\n",
        "task_code": task_code.strip() + "\n",
        "cases": cases,
        "render_test": render_test,
        "oracle": oracle,
        "result_type": result_type,
    }


def task_specs():
    return [
        task(
            "sum-positive",
            "Compute the sum of all strictly positive integers in the input list.",
            r"""
sum_positive = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> if (> h 0) then + h (f t) else f t
    end
);
main = single_pass sum_positive;
""",
            lambda xs: sum(x for x in xs if x > 0),
        ),
        task(
            "count-negative",
            "Count how many integers in the input list are strictly negative.",
            r"""
count_negative = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> if (< h 0) then + 1 (f t) else f t
    end
);
main = single_pass count_negative;
""",
            lambda xs: sum(x < 0 for x in xs),
        ),
        task(
            "count-even",
            "Count how many integers in the input list are even.",
            r"""
count_even = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} ->
        if (== (* (/ h 2) 2) h) then + 1 (f t) else f t
    end
);
main = single_pass count_even;
""",
            lambda xs: sum(x % 2 == 0 for x in xs),
        ),
        task(
            "count-greater-three",
            "Count the list elements that are greater than three.",
            r"""
count_greater_three = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> if (> h 3) then + 1 (f t) else f t
    end
);
main = single_pass count_greater_three;
""",
            lambda xs: sum(x > 3 for x in xs),
        ),
        task(
            "sum-squares",
            "Compute the sum of the squares of all integers in the list.",
            r"""
sum_squares = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> + (* h h) (f t)
    end
);
main = single_pass sum_squares;
""",
            lambda xs: sum(x * x for x in xs),
        ),
        task(
            "sum-absolute",
            "Compute the sum of the absolute values of the list elements.",
            r"""
absolute = \x: Int. if (< x 0) then - 0 x else x;
sum_absolute = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> + (absolute h) (f t)
    end
);
main = single_pass sum_absolute;
""",
            lambda xs: sum(abs(x) for x in xs),
        ),
        task(
            "count-in-range",
            "Count elements in the inclusive range from minus two to three.",
            r"""
count_in_range = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} ->
        if (and (>= h (- 0 2)) (<= h 3)) then + 1 (f t) else f t
    end
);
main = single_pass count_in_range;
""",
            lambda xs: sum(-2 <= x <= 3 for x in xs),
        ),
        task(
            "weighted-sum",
            "Multiply each element by its one-based position and sum the products.",
            r"""
weighted = fix (
    \f: Int -> List -> Int. \i: Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> + (* i h) (f (+ i 1) t)
    end
) 1;
main = single_pass weighted;
""",
            lambda xs: sum((i + 1) * x for i, x in enumerate(xs)),
        ),
        task(
            "alternating-sum",
            "Compute an alternating sum, adding the first element and subtracting the second.",
            r"""
alternating = fix (
    \f: Int -> List -> Int. \sign: Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> + (* sign h) (f (- 0 sign) t)
    end
) 1;
main = single_pass alternating;
""",
            lambda xs: sum(x if i % 2 == 0 else -x for i, x in enumerate(xs)),
        ),
        task(
            "last-or-zero",
            "Return the final list element, or zero when the input list is empty.",
            r"""
last_or_zero = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} ->
        match t with nil _ -> h | cons {_, _} -> f t end
    end
);
main = single_pass last_or_zero;
""",
            lambda xs: xs[-1] if xs else 0,
        ),
        task(
            "product-nonzero",
            "Multiply all nonzero list elements, returning one if none are nonzero.",
            r"""
product_nonzero = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 1
    | cons {h, t} -> if (== h 0) then f t else * h (f t)
    end
);
main = single_pass product_nonzero;
""",
            lambda xs: product([x for x in xs if x != 0]),
        ),
        task(
            "maximum-floor-zero",
            "Return the maximum list element, using zero as a lower bound.",
            r"""
maximum_floor_zero = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> let rest = (f t) in if (> h rest) then h else rest
    end
);
main = single_pass maximum_floor_zero;
""",
            lambda xs: max([0, *xs]),
        ),
        task(
            "minimum-ceiling-zero",
            "Return the minimum list element, using zero as an upper bound.",
            r"""
minimum_ceiling_zero = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> let rest = (f t) in if (< h rest) then h else rest
    end
);
main = single_pass minimum_ceiling_zero;
""",
            lambda xs: min([0, *xs]),
        ),
        task(
            "clamped-sum",
            "Clamp each element to the range minus five through five, then sum the values.",
            r"""
clamp = \x: Int.
    if (< x (- 0 5)) then - 0 5 else if (> x 5) then 5 else x;
clamped_sum = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> + (clamp h) (f t)
    end
);
main = single_pass clamped_sum;
""",
            lambda xs: sum(max(-5, min(5, x)) for x in xs),
        ),
        task(
            "sum-even-positions",
            "Sum elements at zero-based even positions in the list.",
            r"""
sum_even_positions = fix (
    \f: Int -> List -> Int. \i: Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} ->
        if (== (* (/ i 2) 2) i) then + h (f (+ i 1) t)
        else f (+ i 1) t
    end
) 0;
main = single_pass sum_even_positions;
""",
            lambda xs: sum(x for i, x in enumerate(xs) if i % 2 == 0),
        ),
        task(
            "count-zero",
            "Count the number of zero-valued elements in the input list.",
            r"""
count_zero = fix (
    \f: List -> Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} -> if (== h 0) then + 1 (f t) else f t
    end
);
main = single_pass count_zero;
""",
            lambda xs: xs.count(0),
        ),
        task(
            "count-changes",
            "Count adjacent positions whose values differ from the preceding value.",
            r"""
changes_after = fix (
    \f: Int -> List -> Int. \previous: Int. \xs: List.
    match xs with
      nil _ -> 0
    | cons {h, t} ->
        if (== h previous) then f h t else + 1 (f h t)
    end
);
count_changes = \xs: List.
    match xs with nil _ -> 0 | cons {h, t} -> changes_after h t end;
main = single_pass count_changes;
""",
            lambda xs: sum(a != b for a, b in zip(xs, xs[1:])),
        ),
        task(
            "longest-positive-run",
            "Return the length of the longest contiguous run of positive integers.",
            r"""
max_int = \a: Int. \b: Int. if (> a b) then a else b;
positive_runs = fix (
    \f: List -> {Int, Int}. \xs: List.
    match xs with
      nil _ -> {0, 0}
    | cons {h, t} ->
        let rest = (f t) in
            if (> h 0) then {+ 1 rest.1, max_int (+ 1 rest.1) rest.2}
            else {0, rest.2}
    end
);
longest_positive_run = \xs: List. (positive_runs xs).2;
main = single_pass longest_positive_run;
""",
            longest_positive_run,
        ),
        task(
            "contains-large",
            "Return true when any list element has absolute value greater than nine.",
            r"""
contains_large = fix (
    \f: List -> Bool. \xs: List.
    match xs with
      nil _ -> false
    | cons {h, t} ->
        if (or (> h 9) (< h (- 0 9))) then true else f t
    end
);
main = single_pass_bool contains_large;
""",
            lambda xs: any(abs(x) > 9 for x in xs),
            "Bool",
        ),
        task(
            "all-nonnegative",
            "Return true exactly when every integer in the list is nonnegative.",
            r"""
all_nonnegative = fix (
    \f: List -> Bool. \xs: List.
    match xs with
      nil _ -> true
    | cons {h, t} -> if (< h 0) then false else f t
    end
);
main = single_pass_bool all_nonnegative;
""",
            lambda xs: all(x >= 0 for x in xs),
            "Bool",
        ),
        task(
            "contains-zero",
            "Return true when the input list contains at least one zero.",
            r"""
contains_zero = fix (
    \f: List -> Bool. \xs: List.
    match xs with
      nil _ -> false
    | cons {h, t} -> if (== h 0) then true else f t
    end
);
main = single_pass_bool contains_zero;
""",
            lambda xs: 0 in xs,
            "Bool",
        ),
        task(
            "strictly-increasing",
            "Return true when each list element is strictly greater than its predecessor.",
            r"""
increasing_after = fix (
    \f: Int -> List -> Bool. \previous: Int. \xs: List.
    match xs with
      nil _ -> true
    | cons {h, t} -> if (> h previous) then f h t else false
    end
);
strictly_increasing = \xs: List.
    match xs with nil _ -> true | cons {h, t} -> increasing_after h t end;
main = single_pass_bool strictly_increasing;
""",
            lambda xs: all(a < b for a, b in zip(xs, xs[1:])),
            "Bool",
        ),
    ]


def product(values):
    result = 1
    for value in values:
        result *= value
    return result


def longest_positive_run(values):
    best = current = 0
    for value in values:
        current = current + 1 if value > 0 else 0
        best = max(best, current)
    return best


TREE_CASES = [
    None,
    (1, None, None),
    (-1, None, None),
    (3, (1, None, None), (2, None, None)),
    (0, (-2, None, None), (5, None, None)),
    (7, (7, None, None), None),
    (4, (3, (2, None, None), None), None),
    (-5, (-2, None, None), (-8, None, None)),
    (1, (2, (4, None, None), (5, None, None)), (3, None, None)),
    (10, (0, None, (6, None, None)), (-10, None, None)),
]
PAIR_CASES = [
    ([], []),
    ([1], [1]),
    ([1], [-1]),
    ([1, 2, 3], [4, 5, 6]),
    ([1, 2], [1, 2, 3]),
    ([-2, 0, 4], [3, 0, -1]),
    ([2, 2, 2], [2, 3, 2]),
    ([10, -10], [-10, 10]),
    ([1, 2, 1], [1, 2, 1]),
    ([], [1, 2]),
]


def tree_literal(tree):
    if tree is None:
        return "(empty unit)"
    value, left, right = tree
    return (
        f"(node {{{integer(value)}, {tree_literal(left)}, {tree_literal(right)}}})"
    )


def tree_values(tree):
    if tree is None:
        return []
    value, left, right = tree
    return [value, *tree_values(left), *tree_values(right)]


def tree_height(tree):
    if tree is None:
        return 0
    return 1 + max(tree_height(tree[1]), tree_height(tree[2]))


def tree_leaf_count(tree):
    if tree is None:
        return 0
    if tree[1] is None and tree[2] is None:
        return 1
    return tree_leaf_count(tree[1]) + tree_leaf_count(tree[2])


def tree_balanced(tree):
    if tree is None:
        return True
    return (
        abs(tree_height(tree[1]) - tree_height(tree[2])) <= 1
        and tree_balanced(tree[1])
        and tree_balanced(tree[2])
    )


def structural_task_specs():
    tree_int_lib = f"{TREE_DECL}{TREE_INT_WRAPPER}"
    tree_bool_lib = f"{TREE_DECL}{TREE_BOOL_WRAPPER}"
    pair_int_lib = f"{LIST_DECL}{PAIR_INT_WRAPPER}"
    pair_bool_lib = f"{LIST_DECL}{PAIR_BOOL_WRAPPER}"
    render_tree = lambda value: f"main {tree_literal(value)};"
    render_pair = lambda value: (
        f"main {list_literal(value[0])} {list_literal(value[1])};"
    )
    return [
        structural_task(
            "synthetic-tree-sum",
            "Compute the sum of all integer labels in a binary tree.",
            tree_int_lib,
            r"""
tree_sum = fix (
    \f: Tree -> Int. \t: Tree.
    match t with
      empty _ -> 0
    | node {w, l, r} -> + w (+ (f l) (f r))
    end
);
main = tree_pass tree_sum;
""",
            TREE_CASES,
            render_tree,
            lambda tree: sum(tree_values(tree)),
        ),
        structural_task(
            "synthetic-tree-node-count",
            "Count the non-empty nodes in a binary tree.",
            tree_int_lib,
            r"""
node_count = fix (
    \f: Tree -> Int. \t: Tree.
    match t with
      empty _ -> 0
    | node {_, l, r} -> + 1 (+ (f l) (f r))
    end
);
main = tree_pass node_count;
""",
            TREE_CASES,
            render_tree,
            lambda tree: len(tree_values(tree)),
        ),
        structural_task(
            "synthetic-tree-height",
            "Compute the height of a binary tree, with an empty tree having height zero.",
            tree_int_lib,
            r"""
max_int = \a: Int. \b: Int. if (> a b) then a else b;
height = fix (
    \f: Tree -> Int. \t: Tree.
    match t with
      empty _ -> 0
    | node {_, l, r} -> + 1 (max_int (f l) (f r))
    end
);
main = tree_pass height;
""",
            TREE_CASES,
            render_tree,
            tree_height,
        ),
        structural_task(
            "synthetic-tree-leaf-count",
            "Count nodes that have two empty children.",
            tree_int_lib,
            r"""
leaf_count = fix (
    \f: Tree -> Int. \t: Tree.
    match t with
      empty _ -> 0
    | node {_, l, r} ->
        match l with
          empty _ -> match r with empty _ -> 1 | node {_, _, _} -> f r end
        | node {_, _, _} -> + (f l) (f r)
        end
    end
);
main = tree_pass leaf_count;
""",
            TREE_CASES,
            render_tree,
            tree_leaf_count,
        ),
        structural_task(
            "synthetic-tree-positive-count",
            "Count tree nodes whose integer label is strictly positive.",
            tree_int_lib,
            r"""
positive_count = fix (
    \f: Tree -> Int. \t: Tree.
    match t with
      empty _ -> 0
    | node {w, l, r} ->
        if (> w 0) then + 1 (+ (f l) (f r)) else + (f l) (f r)
    end
);
main = tree_pass positive_count;
""",
            TREE_CASES,
            render_tree,
            lambda tree: sum(value > 0 for value in tree_values(tree)),
        ),
        structural_task(
            "synthetic-tree-even-count",
            "Count tree nodes whose integer label is even.",
            tree_int_lib,
            r"""
even_count = fix (
    \f: Tree -> Int. \t: Tree.
    match t with
      empty _ -> 0
    | node {w, l, r} ->
        if (== (* (/ w 2) 2) w) then + 1 (+ (f l) (f r))
        else + (f l) (f r)
    end
);
main = tree_pass even_count;
""",
            TREE_CASES,
            render_tree,
            lambda tree: sum(value % 2 == 0 for value in tree_values(tree)),
        ),
        structural_task(
            "synthetic-tree-contains-seven",
            "Return true when a binary tree contains a node labeled seven.",
            tree_bool_lib,
            r"""
contains_seven = fix (
    \f: Tree -> Bool. \t: Tree.
    match t with
      empty _ -> false
    | node {w, l, r} -> if (== w 7) then true else or (f l) (f r)
    end
);
main = tree_pass_bool contains_seven;
""",
            TREE_CASES,
            render_tree,
            lambda tree: 7 in tree_values(tree),
            "Bool",
        ),
        structural_task(
            "synthetic-tree-all-nonnegative",
            "Return true when every node label in a binary tree is nonnegative.",
            tree_bool_lib,
            r"""
all_nonnegative = fix (
    \f: Tree -> Bool. \t: Tree.
    match t with
      empty _ -> true
    | node {w, l, r} ->
        if (< w 0) then false else and (f l) (f r)
    end
);
main = tree_pass_bool all_nonnegative;
""",
            TREE_CASES,
            render_tree,
            lambda tree: all(value >= 0 for value in tree_values(tree)),
            "Bool",
        ),
        structural_task(
            "synthetic-tree-balanced",
            "Return true when the heights of sibling subtrees differ by at most one everywhere.",
            tree_bool_lib,
            r"""
max_int = \a: Int. \b: Int. if (> a b) then a else b;
absolute = \x: Int. if (< x 0) then - 0 x else x;
metrics = fix (
    \f: Tree -> {Int, Bool}. \t: Tree.
    match t with
      empty _ -> {0, true}
    | node {_, l, r} ->
        let left = (f l) in
            let right = (f r) in
                {+ 1 (max_int left.1 right.1),
                 and left.2 (and right.2 (<= (absolute (- left.1 right.1)) 1))}
    end
);
balanced = \t: Tree. (metrics t).2;
main = tree_pass_bool balanced;
""",
            TREE_CASES,
            render_tree,
            tree_balanced,
            "Bool",
        ),
        structural_task(
            "synthetic-tree-weighted-depth-sum",
            "Sum each tree label multiplied by its one-based depth.",
            tree_int_lib,
            r"""
weighted_depth = fix (
    \f: Int -> Tree -> Int. \depth: Int. \t: Tree.
    match t with
      empty _ -> 0
    | node {w, l, r} ->
        + (* depth w) (+ (f (+ depth 1) l) (f (+ depth 1) r))
    end
) 1;
main = tree_pass weighted_depth;
""",
            TREE_CASES,
            render_tree,
            lambda tree: weighted_tree_sum(tree, 1),
        ),
        structural_task(
            "synthetic-pair-dot-product",
            "Compute the dot product of two lists up to the end of the shorter list.",
            pair_int_lib,
            r"""
dot_product = fix (
    \f: List -> List -> Int. \a: List. \b: List.
    match a with
      nil _ -> 0
    | cons {x, xs} ->
        match b with nil _ -> 0 | cons {y, ys} -> + (* x y) (f xs ys) end
    end
);
main = pair_pass dot_product;
""",
            PAIR_CASES,
            render_pair,
            lambda pair: sum(a * b for a, b in zip(*pair)),
        ),
        structural_task(
            "synthetic-pair-equal-positions",
            "Count positions containing equal values in two lists up to the shorter length.",
            pair_int_lib,
            r"""
equal_positions = fix (
    \f: List -> List -> Int. \a: List. \b: List.
    match a with
      nil _ -> 0
    | cons {x, xs} ->
        match b with
          nil _ -> 0
        | cons {y, ys} -> if (== x y) then + 1 (f xs ys) else f xs ys
        end
    end
);
main = pair_pass equal_positions;
""",
            PAIR_CASES,
            render_pair,
            lambda pair: sum(a == b for a, b in zip(*pair)),
        ),
        structural_task(
            "synthetic-pair-distance",
            "Sum absolute element-wise differences up to the end of the shorter list.",
            pair_int_lib,
            r"""
absolute = \x: Int. if (< x 0) then - 0 x else x;
pair_distance = fix (
    \f: List -> List -> Int. \a: List. \b: List.
    match a with
      nil _ -> 0
    | cons {x, xs} ->
        match b with
          nil _ -> 0
        | cons {y, ys} -> + (absolute (- x y)) (f xs ys)
        end
    end
);
main = pair_pass pair_distance;
""",
            PAIR_CASES,
            render_pair,
            lambda pair: sum(abs(a - b) for a, b in zip(*pair)),
        ),
        structural_task(
            "synthetic-pair-sum-difference",
            "Subtract the sum of the second list from the sum of the first list.",
            pair_int_lib,
            r"""
list_sum = fix (
    \f: List -> Int. \xs: List.
    match xs with nil _ -> 0 | cons {h, t} -> + h (f t) end
);
sum_difference = \a: List. \b: List. - (list_sum a) (list_sum b);
main = pair_pass sum_difference;
""",
            PAIR_CASES,
            render_pair,
            lambda pair: sum(pair[0]) - sum(pair[1]),
        ),
        structural_task(
            "synthetic-pair-common-prefix",
            "Return the length of the common equal prefix of two integer lists.",
            pair_int_lib,
            r"""
common_prefix = fix (
    \f: List -> List -> Int. \a: List. \b: List.
    match a with
      nil _ -> 0
    | cons {x, xs} ->
        match b with
          nil _ -> 0
        | cons {y, ys} -> if (== x y) then + 1 (f xs ys) else 0
        end
    end
);
main = pair_pass common_prefix;
""",
            PAIR_CASES,
            render_pair,
            common_prefix_length,
        ),
        structural_task(
            "synthetic-pair-same-length",
            "Return true exactly when two integer lists have the same length.",
            pair_bool_lib,
            r"""
same_length = fix (
    \f: List -> List -> Bool. \a: List. \b: List.
    match a with
      nil _ -> match b with nil _ -> true | cons {_, _} -> false end
    | cons {_, xs} ->
        match b with nil _ -> false | cons {_, ys} -> f xs ys end
    end
);
main = pair_pass_bool same_length;
""",
            PAIR_CASES,
            render_pair,
            lambda pair: len(pair[0]) == len(pair[1]),
            "Bool",
        ),
        structural_task(
            "synthetic-pair-pointwise-less",
            "Return true when every aligned element of the first list is smaller than the second.",
            pair_bool_lib,
            r"""
pointwise_less = fix (
    \f: List -> List -> Bool. \a: List. \b: List.
    match a with
      nil _ -> true
    | cons {x, xs} ->
        match b with
          nil _ -> false
        | cons {y, ys} -> if (< x y) then f xs ys else false
        end
    end
);
main = pair_pass_bool pointwise_less;
""",
            PAIR_CASES,
            render_pair,
            lambda pair: len(pair[0]) <= len(pair[1])
            and all(a < b for a, b in zip(*pair)),
            "Bool",
        ),
        structural_task(
            "synthetic-pair-same-sum",
            "Return true when two integer lists have equal sums.",
            pair_bool_lib,
            r"""
list_sum = fix (
    \f: List -> Int. \xs: List.
    match xs with nil _ -> 0 | cons {h, t} -> + h (f t) end
);
same_sum = \a: List. \b: List. == (list_sum a) (list_sum b);
main = pair_pass_bool same_sum;
""",
            PAIR_CASES,
            render_pair,
            lambda pair: sum(pair[0]) == sum(pair[1]),
            "Bool",
        ),
    ]


def weighted_tree_sum(tree, depth):
    if tree is None:
        return 0
    return (
        depth * tree[0]
        + weighted_tree_sum(tree[1], depth + 1)
        + weighted_tree_sum(tree[2], depth + 1)
    )


def common_prefix_length(pair):
    count = 0
    for left, right in zip(*pair):
        if left != right:
            break
        count += 1
    return count


def scalar_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_tests(spec):
    cases = spec.get("cases", COMMON_CASES)
    render_test = spec.get("render_test", lambda values: f"main {list_literal(values)};")
    tests = "\n".join(render_test(values) for values in cases)
    expected = [spec["oracle"](values) for values in cases]
    return tests + "\n", expected


def run_executor(code, timeout):
    executor = sufu_model.get_sufu_surface_executor()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".f", prefix="prooft5_sufu_", delete=False
    ) as f:
        path = Path(f.name)
        f.write(sufu_model.replace_ptree(code))
    try:
        ocamlrun = shutil.which("ocamlrun")
        command = [ocamlrun, executor, str(path)] if ocamlrun else [executor, str(path)]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip()[:1200])
        return result.stdout
    finally:
        path.unlink(missing_ok=True)


def extract_scalars(output):
    values = []
    for line in output.splitlines():
        match = re.fullmatch(r"\s*(-?\d+|true|false)\s*:\s*(Int|Bool)\s*", line)
        if match:
            raw, value_type = match.groups()
            values.append(raw == "true" if value_type == "Bool" else int(raw))
    return values


def convert_spec(spec, tokenizer, grammar_tokenizer, rules, timeout):
    tests, expected = build_tests(spec)
    code = f"{spec['lib_code']}\n{spec['task_code']}"
    output = run_executor(f"{code}\n{tests}", timeout)
    actual = extract_scalars(output)[-len(expected):]
    if actual != expected:
        raise RuntimeError(f"oracle mismatch: expected {expected}, got {actual}")

    node = sufu_model.parser.parse(code.encode()).root_node
    if node.has_error:
        raise RuntimeError("tree-sitter parse contains an error node")
    program = sufu_model.visit(node, {"code": code})
    program.type_check(sufu_model.TypeCtx())
    tokens = program.tokenize()
    tokens = grammar_tokenizer.convert_ids_to_tokens(
        grammar_tokenizer.convert_tokens_to_ids(tokens)
    )
    missing = sorted({token for token in tokens if token not in rules})
    if missing:
        raise KeyError(f"fixed vocabulary is missing {missing[:10]}")

    decoded, _ = sufu_model.detokenize(tokens)
    reconstructed = decoded.to_str({})
    reconstructed_output = run_executor(f"{reconstructed}\n{tests}", timeout)
    reconstructed_values = extract_scalars(reconstructed_output)[-len(expected):]
    if reconstructed_values != expected:
        raise RuntimeError(
            f"detokenized program mismatch: expected {expected}, got {reconstructed_values}"
        )

    library_node = sufu_model.parser.parse(spec["lib_code"].encode()).root_node
    library = sufu_model.visit(library_node, {"code": spec["lib_code"]})
    prefix_tokens = library.tokenize()[:-1]
    prefix_tokens = grammar_tokenizer.convert_ids_to_tokens(
        grammar_tokenizer.convert_tokens_to_ids(prefix_tokens)
    )
    if tokens[:len(prefix_tokens)] != prefix_tokens:
        raise RuntimeError("library prefix does not match full program tokens")

    token_ids = [rules[token] for token in tokens]
    prefix = [rules[token] for token in prefix_tokens]
    return {
        "file_name": spec["file_name"],
        "nl": tokenizer.encode(spec["desc"]),
        "nl_raw": f"**{spec['desc']}**",
        "rulelist": [tokenizer.bos_token_id, *token_ids, tokenizer.eos_token_id],
        "prefix": prefix,
        "prefix_raw": spec["lib_code"],
        "postfix": token_ids[len(prefix):],
        "postfix_raw": spec["task_code"],
        "code": code,
        "tests": tests,
        "output": output,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-task", default=DEFAULT_REFERENCE_TASK)
    parser.add_argument(
        "--grammar-task",
        default="sufucoq",
        help="Legacy SuFu tokenizer used by the incremental grammar parser.",
    )
    parser.add_argument("--output-root", type=Path, default=ROOT / "Utils" / "data")
    parser.add_argument("--date-tag", default="20260730")
    parser.add_argument("--suite", choices=["v1", "structural-v2"], default="v1")
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main():
    args = parse_args()
    reference = ROOT / "Utils" / "data" / args.reference_task
    destination_name = (
        f"sufu_synthetic_external_t5gemma2_{args.date_tag}"
        if args.suite == "v1"
        else f"sufu_synthetic_structural_v2_t5gemma2_{args.date_tag}"
    )
    destination = args.output_root / destination_name
    if destination.exists():
        raise FileExistsError(f"refusing to replace existing dataset: {destination}")
    destination.mkdir(parents=True)

    tokenizer = load_pickle(reference / "tokenizer.pkl")
    # sufu_model reconstructs this legacy tokenizer from the local CodeT5 files
    # when the old fast-tokenizer pickle cannot be imported by modern Transformers.
    grammar_tokenizer = sufu_model.tokenizer
    rules = load_pickle(reference / "rules.pkl")
    sufu_model.tokenizer = grammar_tokenizer
    converted = []
    report = []
    source_programs = []
    specs = task_specs() if args.suite == "v1" else structural_task_specs()
    for spec in specs:
        tests, expected = build_tests(spec)
        source_programs.append(
            {
                key: value
                for key, value in spec.items()
                if key not in {"oracle", "render_test"}
            }
            | {"tests": tests, "expected": [scalar_text(value) for value in expected]}
        )
        try:
            converted.append(
                convert_spec(
                    spec, tokenizer, grammar_tokenizer, rules, args.timeout
                )
            )
            report.append({"task_id": spec["file_name"], "status": "passed"})
        except Exception as exc:
            report.append(
                {
                    "task_id": spec["file_name"],
                    "status": "failed",
                    "stage_error": f"{type(exc).__name__}: {exc}"[:1200],
                }
            )
        print(f"{spec['file_name']}: {report[-1]['status']}")

    if not converted:
        raise RuntimeError("no SuFu task passed validation")
    dump_pickle([], destination / "train.pkl")
    dump_pickle([], destination / "valid.pkl")
    dump_pickle(converted, destination / "test.pkl")
    dump_pickle(converted, destination / "all_candidates.pkl")
    dump_json([], destination / "train.json")
    dump_json([], destination / "valid.json")
    dump_json(converted, destination / "test.json")
    dump_json(source_programs, destination / "source_programs.json")
    for filename in ["rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl"]:
        shutil.copy2(reference / filename, destination / filename)

    config = json.loads((reference / "config.json").read_text())
    config.update(
        {
            "evaluation_only": True,
            "validation": False,
            "batch_size_eval": 1,
            "rulenum": len(rules),
            "CodeLen": max(len(row["rulelist"]) for row in converted),
            "max_code_len": max(
                len(row["rulelist"]) - len(row["prefix"]) for row in converted
            ),
        }
    )
    dump_json(config, destination / "config.json")
    dump_json(
        {
            "dataset": destination.name,
            "suite": args.suite,
            "policy": "held-out evaluation only",
            "reference_task": reference.name,
            "grammar_tokenizer_task": args.grammar_task,
            "fixed_vocabulary_size": len(rules),
            "checked": len(report),
            "passed": len(converted),
            "failed": len(report) - len(converted),
            "tests_per_task": len(COMMON_CASES),
            "rows": report,
        },
        destination / "conversion_report.json",
    )
    print(f"{destination}: {len(converted)}/{len(report)} passed")


if __name__ == "__main__":
    main()
