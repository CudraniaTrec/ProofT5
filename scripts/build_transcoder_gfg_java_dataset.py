#!/usr/bin/env python3
"""Build an MBJP-shaped, fixed-test TransCoder-GFG Java candidate pool.

The upstream TransCoder Java scripts contain a ``f_gold`` method and a test
harness that compares a generated ``f_filled`` method with that oracle.  This
builder turns each script into a self-contained natural-language-to-method
task, freezes the oracle results into deterministic tests, and then subjects
the canonical method to the normal ProofT5 Java/Coq/token round trip.

No train/test split is created here.  Near-duplicate ``_1``/``_2`` variants
share a group id so a later split can keep them on the same side.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import json
import pickle
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "coq_model"))

import java2impp  # noqa: E402
import myjavalang as javalang  # noqa: E402
import program_model  # noqa: E402
from beamsearch_coq import configure_runtime  # noqa: E402
from scripts.build_java_external_datasets import (  # noqa: E402
    DEFAULT_REFERENCE_TASK,
    build_dataset,
    load_pickle,
)


DEFAULT_TRANSCODER_ROOT = Path("/data2/x/hzc/.local/src/TransCoder")
SOURCE_SUBDIR = Path(
    "data/evaluation/geeks_for_geeks_successful_test_scripts/java"
)
TITLE_PREFIXES = (
    "RECURSIVE_C_PROGRAM_",
    "WRITE_A_C_PROGRAM_TO_",
    "WRITE_AN_EFFICIENT_METHOD_TO_",
    "C_PROGRAM_",
    "PROGRAM_TO_",
    "PROGRAM_FOR_",
    "PROGRAM_",
)
TITLE_OVERRIDES = {
    "ANALYSIS_OF_ALGORITHMS_SET_2_ASYMPTOTIC_ANALYSIS":
        "find the first occurrence of a value among the first n array elements",
    "DYNAMIC_PROGRAMMING_HIGH_EFFORT_VS_LOW_EFFORT_TASKS_PROBLEM":
        "find the maximum task reward by choosing high-effort or low-effort work each day",
    "HORNERS_METHOD_POLYNOMIAL_EVALUATION":
        "evaluate a polynomial using Horner's method",
    "PAIR_WITH_GIVEN_PRODUCT_SET_1_FIND_IF_ANY_PAIR_EXISTS":
        "check whether an array contains a pair with a given product",
    "PRIMALITY_TEST_SET_1_INTRODUCTION_AND_SCHOOL_METHOD":
        "check whether a number is prime using trial division",
}
JAVA_KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch",
    "char", "class", "const", "continue", "default", "do", "double",
    "else", "enum", "extends", "final", "finally", "float", "for",
    "goto", "if", "implements", "import", "instanceof", "int",
    "interface", "long", "native", "new", "package", "private",
    "protected", "public", "return", "short", "static", "strictfp",
    "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while",
}


OBSERVATION_HELPERS = r"""
    static String encodeValue(Object value) {
        if (value == null) return "N";
        if (value instanceof String) {
            return "S" + Base64.getEncoder().encodeToString(
                ((String) value).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
        if (value instanceof Character) return "C" + (int) ((Character) value);
        if (value instanceof Boolean) return ((Boolean) value) ? "Z1" : "Z0";
        if (value instanceof Byte) return "B" + value;
        if (value instanceof Short) return "H" + value;
        if (value instanceof Integer) return "I" + value;
        if (value instanceof Long) return "J" + value;
        if (value instanceof Float) {
            return "F" + Integer.toUnsignedString(
                Float.floatToIntBits((Float) value));
        }
        if (value instanceof Double) {
            return "D" + Long.toUnsignedString(
                Double.doubleToLongBits((Double) value));
        }
        Class<?> cls = value.getClass();
        if (cls.isArray()) {
            int length = java.lang.reflect.Array.getLength(value);
            StringBuilder out = new StringBuilder("A" + length + "[");
            for (int i = 0; i < length; i++) {
                String item = encodeValue(java.lang.reflect.Array.get(value, i));
                out.append(item.length()).append(':').append(item);
            }
            return out.append(']').toString();
        }
        if (value instanceof Map<?, ?>) {
            List<String> entries = new ArrayList<>();
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                entries.add(encodeValue(entry.getKey()) + "="
                    + encodeValue(entry.getValue()));
            }
            Collections.sort(entries);
            return "M" + encodeValue(entries.toArray(new String[0]));
        }
        if (value instanceof Collection<?>) {
            Collection<?> collection = (Collection<?>) value;
            List<String> items = new ArrayList<>();
            for (Object item : collection) items.add(encodeValue(item));
            if (value instanceof Set<?>) Collections.sort(items);
            return "L" + encodeValue(items.toArray(new String[0]));
        }
        return "O" + value.getClass().getName() + ":" + value;
    }

    static String observe(Object result, Object... arguments) {
        return "R" + encodeValue(result) + ";A" + encodeValue(arguments);
    }

    static String encodeObservation(Object result, Object... arguments) {
        return Base64.getEncoder().encodeToString(
            observe(result, arguments).getBytes(
                java.nio.charset.StandardCharsets.UTF_8));
    }
"""

HELPER_IMPORTS = """import java.lang.reflect.Array;
import java.nio.charset.StandardCharsets;
import java.util.*;
"""


@dataclass
class ExtractedTask:
    source_path: Path
    source_stem: str
    group_id: str
    variant: int
    class_name: str
    method_name: str
    parameter_names: list[str]
    return_is_void: bool
    original_method: str
    canonical_method: str
    setup: str
    argument_expressions: list[list[str]]
    description: str
    difficulty: str
    nonblank_loc: int
    source_sha256: str
    normalized_method_sha256: str
    compatibility_modifications: list[str]


def remove_stdout_statements(method: str) -> tuple[str, int]:
    """Remove standalone System.out.print* calls from an oracle method.

    GFG uses these calls as demonstrations in a few otherwise return-valued
    functions.  They are not part of the benchmark method contract and would
    corrupt the line-oriented frozen-observation channel.
    """
    pattern = re.compile(r"\bSystem\s*\.\s*out\s*\.\s*(?:print|println|printf)\s*\(")
    removed = 0
    cursor = 0
    pieces: list[str] = []
    while True:
        match = pattern.search(method, cursor)
        if match is None:
            pieces.append(method[cursor:])
            break
        opening = method.find("(", match.start())
        closing = matching_delimiter(method, opening, "(", ")")
        semicolon = closing + 1
        while semicolon < len(method) and method[semicolon].isspace():
            semicolon += 1
        if semicolon >= len(method) or method[semicolon] != ";":
            pieces.append(method[cursor:closing + 1])
            cursor = closing + 1
            continue
        pieces.append(method[cursor:match.start()])
        cursor = semicolon + 1
        removed += 1
    return "".join(pieces), removed


def normalize_array_declarators(method: str) -> tuple[str, int]:
    """Convert C-style ``int a[]`` declarations to ``int[] a``."""
    primitive_or_string = r"(?:boolean|byte|char|short|int|long|float|double|String)"
    pattern = re.compile(
        rf"\b({primitive_or_string})\s+([A-Za-z_$][\w$]*)\s+((?:\[\s*\]\s*)+)"
    )
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        dimensions = re.sub(r"\s+", "", match.group(3))
        return f"{match.group(1)} {dimensions} {match.group(2)} "

    return pattern.sub(replace, method), count


def normalize_external_for_initializers(method: str) -> tuple[str, int]:
    """Make assignment-style for initializers representable by java2impp.

    java2impp accepts a variable declaration as a for initializer but treats a
    Java expression-list initializer as an unsupported AST list.  Introducing
    an unused initializer variable preserves execution of the assignment and
    keeps the original loop variable visible after the loop.
    """
    pattern = re.compile(
        r"\bfor\s*\(\s*([A-Za-z_$][\w$]*)\s*=\s*([^;]+?)\s*;"
    )
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        name = match.group(1)
        initializer = match.group(2).strip()
        replacement = (
            f"for ( int __gfgInit{count} = ( {name} = {initializer} ) ;"
        )
        count += 1
        return replacement

    return pattern.sub(replace, method), count


def normalize_for_control_shape(method: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    dummy = 0

    def add_dummy(match: re.Match[str]) -> str:
        nonlocal dummy
        replacement = f"for ( int __gfgEmptyInit{dummy} = 0 ;"
        dummy += 1
        return replacement

    method, empty_init_count = re.subn(r"\bfor\s*\(\s*;", add_dummy, method)
    if empty_init_count:
        changes.append(f"empty_for_initializers:{empty_init_count}")

    method, empty_condition_count = re.subn(r";\s*;", "; true ;", method)
    if empty_condition_count:
        changes.append(f"empty_for_conditions:{empty_condition_count}")

    # Encode two unit updates as one Java expression while preserving both
    # side effects.  Multiplication by zero makes the second variable's value
    # irrelevant but still executes its increment/decrement.
    update_pattern = re.compile(
        r"\b([A-Za-z_$][\w$]*)\s*(\+\+|--)\s*,\s*"
        r"([A-Za-z_$][\w$]*)\s*(\+\+|--)\s*\)"
    )
    prefix_pattern = re.compile(
        r"(\+\+|--)\s*([A-Za-z_$][\w$]*)\s*,\s*"
        r"(\+\+|--)\s*([A-Za-z_$][\w$]*)\s*\)"
    )

    def fold_postfix(match: re.Match[str]) -> str:
        first, first_op, second, second_op = match.groups()
        assignment = "+=" if first_op == "++" else "-="
        return f"{first} {assignment} ( ( {second} {second_op} ) * 0 + 1 ) )"

    def fold_prefix(match: re.Match[str]) -> str:
        first_op, first, second_op, second = match.groups()
        assignment = "+=" if first_op == "++" else "-="
        return f"{first} {assignment} ( ( {second_op} {second} ) * 0 + 1 ) )"

    method, postfix_count = update_pattern.subn(fold_postfix, method)
    method, prefix_count = prefix_pattern.subn(fold_prefix, method)
    if postfix_count + prefix_count:
        changes.append(f"folded_for_updates:{postfix_count + prefix_count}")
    return method, changes


def normalize_void_to_sentinel(method: str) -> tuple[str, bool]:
    header = re.search(r"\bstatic\s+void\s+f_gold\b", method)
    if header is None:
        return method, False
    method = re.sub(r"\bstatic\s+void\s+f_gold\b", "static int f_gold", method, count=1)
    method = re.sub(r"\breturn\s*;", "return 0;", method)
    closing = method.rfind("}")
    if closing < 0:
        raise ValueError("normalized void method has no closing brace")
    method = method[:closing] + "\n  return 0 ;\n" + method[closing:]
    return method, True


def normalize_numeric_types(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []

    def replace_parse_long(match: re.Match[str]) -> str:
        value = int(match.group(1))
        bounded = max(-1_000_000_000, min(1_000_000_000, value))
        if bounded != value:
            changes.append("bounded_long_test_literal")
        return str(bounded)

    updated = re.sub(
        r"\bLong\s*\.\s*parseLong\s*\(\s*\"(-?\d+)\"\s*\)",
        replace_parse_long,
        text,
    )

    def replace_long_literal(match: re.Match[str]) -> str:
        value = int(match.group(1))
        bounded = min(value, 1_000_000_000)
        if bounded != value:
            changes.append("bounded_long_test_literal")
        return str(bounded)

    updated = re.sub(r"\b(\d+)\s*[lL]\b", replace_long_literal, updated)
    if re.search(r"\blong\b|\bLong\b", updated):
        updated = re.sub(r"\blong\b", "int", updated)
        updated = re.sub(r"\bLong\b", "Integer", updated)
        changes.append("long_to_int")

    if re.search(r"\bfloat\b|\bFloat\b", updated):
        updated = re.sub(r"\bfloat\b", "double", updated)
        updated = re.sub(r"\bFloat\b", "Double", updated)
        updated = re.sub(
            r"\b(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*[fF]\b",
            r"\1",
            updated,
        )
        changes.append("float_to_double")
    return updated, changes


def apply_semantic_compatibility_rewrite(
    source_stem: str, method: str
) -> tuple[str, str | None]:
    replacements = {
        "ADD_1_TO_A_GIVEN_NUMBER_1": """static int f_gold ( int x ) {
  return x + 1 ;
}""",
        "COUNT_SET_BITS_IN_AN_INTEGER": """static int f_gold ( int n ) {
  int count = 0 ;
  while ( n > 0 ) {
    count += n % 2 ;
    n /= 2 ;
  }
  return count ;
}""",
        "HOW_TO_TURN_OFF_A_PARTICULAR_BIT_IN_A_NUMBER": """static int f_gold ( int n , int k ) {
  if ( k <= 0 ) return n ;
  int exponent = ( k - 1 ) % 32 ;
  int mask = 1 ;
  for ( int i = 0 ; i < exponent ; i ++ ) mask *= 2 ;
  if ( n / mask % 2 == 0 ) return n ;
  return n - mask ;
}""",
        "CHECK_CHARACTERS_GIVEN_STRING_CAN_REARRANGED_FORM_PALINDROME_1":
            """static boolean f_gold ( String str ) {
  int odd = 0 ;
  for ( int i = 0 ; i < str . length ( ) ; i ++ ) {
    boolean first = true ;
    for ( int j = 0 ; j < i ; j ++ ) {
      if ( str . charAt ( i ) == str . charAt ( j ) ) first = false ;
    }
    if ( first ) {
      int count = 0 ;
      for ( int j = i ; j < str . length ( ) ; j ++ ) {
        if ( str . charAt ( i ) == str . charAt ( j ) ) count ++ ;
      }
      if ( count % 2 == 1 ) odd ++ ;
    }
  }
  return odd <= 1 ;
}""",
        "CHECK_LARGE_NUMBER_DIVISIBLE_13_NOT": """static boolean f_gold ( String num ) {
  int length = num . length ( ) ;
  if ( length == 1 && num . charAt ( 0 ) == '0' ) return true ;
  if ( length % 3 == 1 ) num += "00" ;
  else if ( length % 3 == 2 ) num += "0" ;
  length = num . length ( ) ;
  int sum = 0 ;
  int sign = 1 ;
  for ( int end = length ; end > 0 ; end -= 3 ) {
    int start = end - 3 ;
    int group = ( num . charAt ( start ) - '0' ) * 100 ;
    group += ( num . charAt ( start + 1 ) - '0' ) * 10 ;
    group += num . charAt ( start + 2 ) - '0' ;
    sum += group * sign ;
    sign *= - 1 ;
  }
  return Math . abs ( sum ) % 13 == 0 ;
}""",
    }
    if source_stem in replacements:
        return replacements[source_stem], source_stem.lower()
    if source_stem == "MINIMUM_STEPS_MINIMIZE_N_PER_GIVEN_CONDITION":
        updated = method.replace("! ( i % 2 > 0 )", "i % 2 == 0")
        updated = updated.replace("! ( i % 3 > 0 )", "i % 3 == 0")
        return updated, source_stem.lower()
    if source_stem == "N_TH_ROOT_NUMBER":
        return method.replace("Math . random ( ) % 10", "1.0"), source_stem.lower()
    return method, None


def compatibility_normalize(
    source_stem: str, method: str, setup: str
) -> tuple[str, str, list[str]]:
    modifications: list[str] = []
    method, semantic_rewrite = apply_semantic_compatibility_rewrite(source_stem, method)
    if semantic_rewrite:
        modifications.append(f"semantic_rewrite:{semantic_rewrite}")
    method, removed = remove_stdout_statements(method)
    if removed:
        modifications.append(f"removed_stdout_statements:{removed}")
    method, arrays = normalize_array_declarators(method)
    if arrays:
        modifications.append(f"c_style_array_declarators:{arrays}")
    method, method_numeric = normalize_numeric_types(method)
    setup, setup_numeric = normalize_numeric_types(setup)
    modifications.extend(method_numeric)
    modifications.extend(setup_numeric)
    method, loops = normalize_external_for_initializers(method)
    if loops:
        modifications.append(f"external_for_initializers:{loops}")
    method, for_changes = normalize_for_control_shape(method)
    modifications.extend(for_changes)
    method, void_changed = normalize_void_to_sentinel(method)
    if void_changed:
        modifications.append("void_to_int_sentinel")
    return method, setup, list(dict.fromkeys(modifications))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def java_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def matching_delimiter(text: str, opening: int, left: str, right: str) -> int:
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    index = opening
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            line_comment = char != "\n"
        elif block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and nxt == "/":
            line_comment = True
            index += 1
        elif char == "/" and nxt == "*":
            block_comment = True
            index += 1
        elif char in {'"', "'"}:
            quote = char
        elif char == left:
            depth += 1
        elif char == right:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError(f"unmatched {left!r} at byte {opening}")


def extract_gold_method(source: str) -> str:
    match = re.search(
        r"\bstatic\s+[^;{}]*?\bf_gold\s*\([^;{}]*\)\s*\{",
        source,
        flags=re.S,
    )
    if match is None:
        raise ValueError("f_gold method not found")
    opening = source.find("{", match.start())
    closing = matching_delimiter(source, opening, "{", "}")
    return source[match.start():closing + 1]


def extract_main_setup(source: str) -> str:
    main = re.search(r"\bpublic\s+static\s+void\s+main\s*\([^)]*\)\s*\{", source)
    if main is None:
        raise ValueError("main method not found")
    opening = source.find("{", main.start())
    closing = matching_delimiter(source, opening, "{", "}")
    body = source[opening + 1:closing]
    success = re.search(r"\bint\s+n_success\s*=\s*0\s*;", body)
    loop = re.search(r"\bfor\s*\(\s*int\s+i\s*=\s*0\s*;", body)
    if success is None or loop is None or loop.start() <= success.end():
        raise ValueError("TransCoder parameter setup not found")
    setup = body[success.end():loop.start()].strip()
    if not setup:
        raise ValueError("empty parameter setup")
    return setup


def extract_add_expressions(setup: str) -> dict[int, list[str]]:
    values: dict[int, list[str]] = {}
    pattern = re.compile(r"\bparam(\d+)\s*\.\s*add\s*\(")
    cursor = 0
    while True:
        match = pattern.search(setup, cursor)
        if match is None:
            break
        opening = setup.find("(", match.start())
        closing = matching_delimiter(setup, opening, "(", ")")
        values.setdefault(int(match.group(1)), []).append(
            setup[opening + 1:closing].strip()
        )
        cursor = closing + 1
    if not values or 0 not in values:
        raise ValueError("no param0.add inputs found")
    sizes = {len(items) for items in values.values()}
    if len(sizes) != 1:
        raise ValueError(f"parameter lists have unequal sizes: {sorted(sizes)}")
    if sorted(values) != list(range(len(values))):
        raise ValueError(f"non-contiguous parameter lists: {sorted(values)}")
    return values


def compute_groups(paths: list[Path]) -> dict[str, str]:
    stems = {path.stem for path in paths}
    numbered: dict[str, list[str]] = {}
    for stem in stems:
        match = re.match(r"^(.*)_(\d+)$", stem)
        if match:
            numbered.setdefault(match.group(1), []).append(stem)
    groups = {}
    for stem in stems:
        match = re.match(r"^(.*)_(\d+)$", stem)
        if match and (
            match.group(2) == "1"
            or match.group(1) in stems
            or len(numbered.get(match.group(1), [])) > 1
        ):
            groups[stem] = match.group(1)
        else:
            groups[stem] = stem
    return groups


def title_words(group: str) -> list[str]:
    if group in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[group].split()
    title = group
    title = re.sub(r"^DYNAMIC_PROGRAMMING_SET_\d+_", "", title)
    title = re.sub(r"^PRIMALITY_TEST_SET_\d+_INTRODUCTION_AND_", "", title)
    title = re.sub(r"^EFFICIENT_WAY_TO_(.*)$", r"\1_EFFICIENTLY", title)
    title = re.sub(r"^EFFICIENT_WAY_(.*)$", r"\1_EFFICIENTLY", title)
    title = re.sub(r"^EFFICIENT_SEARCH_(.*)$", r"SEARCH_EFFICIENTLY_\1", title)
    for prefix in TITLE_PREFIXES:
        if title.startswith(prefix):
            title = title[len(prefix):]
            break
    replacements = {
        "YOU": "YOUR",
        "ARRI": "ARRAY",
        "GRAMMER": "GRAMMAR",
    }
    return [replacements.get(word, word).lower() for word in title.split("_") if word]


def semantic_method_name(group: str, variant: int) -> str:
    words = title_words(group)
    if not words:
        words = ["solve"]
    name = words[0] + "".join(word[:1].upper() + word[1:] for word in words[1:])
    name = re.sub(r"[^A-Za-z0-9_$]", "", name)
    if not name or name[0].isdigit() or name in JAVA_KEYWORDS:
        name = "solve" + name[:1].upper() + name[1:]
    if len(name) > 72:
        digest = hashlib.sha1(group.encode()).hexdigest()[:8]
        name = f"{name[:63]}{digest}"
    if variant:
        name = f"{name}Variant{variant + 1}"
    return name


def natural_description(group: str) -> str:
    phrase = " ".join(title_words(group))
    phrase = re.sub(r"\s+", " ", phrase).strip()
    if not phrase:
        phrase = "solve the specified problem"
    verbs = {
        "add", "calculate", "check", "compute", "concatenate", "convert", "count", "cut",
        "determine", "detect", "evaluate", "find", "generate", "get",
        "multiply", "perform", "print", "remove", "replace", "return", "reverse",
        "search", "sort", "sum", "swap", "test", "verify", "write",
    }
    if phrase.split()[0] in verbs:
        return f"Write a Java method to {phrase}."
    return f"Write a Java method that computes the {phrase}."


def method_metadata(method: str) -> tuple[list[str], bool]:
    wrapped = f"class SignatureProbe {{\n{method}\n}}"
    tree = javalang.parse.parse(wrapped)
    declaration = tree.types[0].methods[0]
    names = [parameter.name for parameter in declaration.parameters]
    return names, declaration.return_type is None


def make_canonical_method(method: str, method_name: str) -> str:
    renamed = re.sub(r"\bf_gold\b", method_name, method)
    if not re.match(r"\s*public\b", renamed):
        renamed = re.sub(r"\bstatic\b", "public static", renamed, count=1)
    return renamed


def build_extracted_task(
    path: Path,
    variant: int,
    group: str | None = None,
    compatibility_normalization: bool = False,
) -> ExtractedTask:
    source = path.read_text(encoding="utf-8", errors="replace")
    original_method = extract_gold_method(source)
    method = original_method
    setup = extract_main_setup(source)
    modifications: list[str] = []
    if compatibility_normalization:
        method, setup, modifications = compatibility_normalize(path.stem, method, setup)
    parameter_names, return_is_void = method_metadata(method)
    by_parameter = extract_add_expressions(setup)
    if len(by_parameter) != len(parameter_names):
        raise ValueError(
            f"signature has {len(parameter_names)} parameters but harness has "
            f"{len(by_parameter)} lists"
        )
    expressions = [by_parameter[index] for index in range(len(by_parameter))]
    group = group or path.stem
    method_name = semantic_method_name(group, variant)
    canonical_method = make_canonical_method(method, method_name)
    nonblank_loc = sum(bool(line.strip()) for line in canonical_method.splitlines())
    difficulty = "easy" if nonblank_loc <= 10 else "medium" if nonblank_loc <= 25 else "hard"
    class_name = "Gfg" + hashlib.sha1(path.stem.encode()).hexdigest()[:12]
    return ExtractedTask(
        source_path=path,
        source_stem=path.stem,
        group_id=group,
        variant=variant,
        class_name=class_name,
        method_name=method_name,
        parameter_names=parameter_names,
        return_is_void=return_is_void,
        original_method=original_method,
        canonical_method=canonical_method,
        setup=setup,
        argument_expressions=expressions,
        description=natural_description(group),
        difficulty=difficulty,
        nonblank_loc=nonblank_loc,
        source_sha256=sha256_text(source),
        normalized_method_sha256=sha256_text(method),
        compatibility_modifications=modifications,
    )


def invocation(task: ExtractedTask, receiver: str, index: str = "i") -> str:
    arguments = ", ".join(
        f"param{position}.get({index})"
        for position in range(len(task.parameter_names))
    )
    return f"{receiver}.{task.method_name}({arguments})"


def oracle_source(task: ExtractedTask) -> str:
    call = invocation(task, "Oracle")
    argument_state = ", ".join(
        f"param{position}.get(i)" for position in range(len(task.parameter_names))
    )
    if task.return_is_void:
        action = f"{call};\n            Object result = null;"
    else:
        action = f"Object result = {call};"
    return f"""{HELPER_IMPORTS}
class Oracle {{
{task.canonical_method}
{OBSERVATION_HELPERS}
    public static void main(String[] args) {{
{task.setup}
        for (int i = 0; i < param0.size(); i++) {{
            {action}
            System.out.println(encodeObservation(result, {argument_state}));
        }}
    }}
}}
"""


def run_oracle(task: ExtractedTask, timeout: int) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="prooft5_gfg_oracle_") as tmp:
        path = Path(tmp) / "Oracle.java"
        path.write_text(oracle_source(task), encoding="utf-8")
        compiled = subprocess.run(
            ["javac", path.name], cwd=tmp, capture_output=True, text=True, timeout=timeout
        )
        if compiled.returncode:
            raise RuntimeError(f"oracle javac: {compiled.stderr.strip()[:800]}")
        executed = subprocess.run(
            ["java", "Oracle"], cwd=tmp, capture_output=True, text=True, timeout=timeout
        )
        if executed.returncode:
            message = (executed.stderr or executed.stdout).strip()
            raise RuntimeError(f"oracle java: {message[:800]}")
        outputs = [line.strip() for line in executed.stdout.splitlines() if line.strip()]
    expected = len(task.argument_expressions[0])
    if len(outputs) != expected:
        raise RuntimeError(f"oracle emitted {len(outputs)} rows, expected {expected}")
    for output in outputs:
        base64.b64decode(output, validate=True)
    return outputs


def human_result(encoded_observation: str) -> str:
    observation = base64.b64decode(encoded_observation).decode("utf-8")
    result = observation.split(";A", 1)[0][1:]
    if result == "N":
        return "void/null"
    prefixes = {
        "Z1": "true", "Z0": "false",
    }
    if result in prefixes:
        return prefixes[result]
    if result.startswith("S"):
        try:
            value = base64.b64decode(result[1:]).decode("utf-8")
            if len(value) > 96:
                value = value[:93] + "..."
            return java_string(value)
        except Exception:
            return result
    if result[:1] in {"B", "H", "I", "J"}:
        return result[1:]
    if result.startswith("C"):
        try:
            return java_string(chr(int(result[1:])))
        except Exception:
            return result
    if result.startswith("F"):
        try:
            bits = int(result[1:])
            return repr(struct.unpack("!f", bits.to_bytes(4, "big"))[0])
        except Exception:
            return result
    if result.startswith("D"):
        try:
            bits = int(result[1:])
            return repr(struct.unpack("!d", bits.to_bytes(8, "big"))[0])
        except Exception:
            return result
    return result[:160]


def example_lines(task: ExtractedTask, outputs: list[str], limit: int = 2) -> list[str]:
    examples = []
    for index in range(min(limit, len(outputs))):
        arguments = ", ".join(
            expressions[index] for expressions in task.argument_expressions
        )
        if len(arguments) > 96:
            arguments = arguments[:93] + "..."
        examples.append(
            f"{task.method_name}({arguments}) returns {human_result(outputs[index])}."
        )
    return examples


def prompt_and_source(
    task: ExtractedTask, outputs: list[str]
) -> tuple[str, str, str]:
    examples = example_lines(task, outputs)
    description = " ".join([task.description, *examples])
    comment_lines = [task.description, "", "Examples:", *[f"- {line}" for line in examples]]
    comment = "\n".join(f"     * {line}" if line else "     *" for line in comment_lines)
    opening = task.canonical_method.find("{")
    header = task.canonical_method[:opening].strip()
    body_and_close = task.canonical_method[opening + 1:]
    prompt = (
        "import java.lang.*;\n"
        "import java.util.*;\n"
        "import java.math.*;\n\n"
        f"class {task.class_name} {{\n"
        "    /**\n"
        f"{comment}\n"
        "     */\n"
        f"    {header} {{\n"
    )
    canonical_solution = f"{body_and_close.rstrip()}\n}}"
    source = prompt + canonical_solution
    return prompt, source, description


def fixed_test(task: ExtractedTask, outputs: list[str]) -> str:
    call = invocation(task, task.class_name)
    argument_state = ", ".join(
        f"param{position}.get(i)" for position in range(len(task.parameter_names))
    )
    if task.return_is_void:
        action = f"{call};\n            Object result = null;"
    else:
        action = f"Object result = {call};"
    expected = ",\n            ".join(java_string(value) for value in outputs)
    return f"""
class Main {{
{OBSERVATION_HELPERS}
    public static void main(String[] args) {{
{task.setup}
        String[] expected = new String[] {{
            {expected}
        }};
        if (expected.length != param0.size()) {{
            throw new AssertionError("test fixture length mismatch");
        }}
        for (int i = 0; i < expected.length; i++) {{
            {action}
            String actual = encodeObservation(result, {argument_state});
            if (!expected[i].equals(actual)) {{
                throw new AssertionError(
                    "case " + i + " failed: expected=" + expected[i]
                    + ", actual=" + actual);
            }}
        }}
    }}
}}
"""


def make_record(task: ExtractedTask, timeout: int) -> tuple[dict, dict]:
    outputs = run_oracle(task, timeout)
    prompt, source, description = prompt_and_source(task, outputs)
    test = fixed_test(task, outputs)
    record = {
        "task_id": f"TransCoderGFG/{task.source_stem}",
        "prompt": prompt,
        "description": description,
        "source": source,
        "test": test,
        "source_file": str(task.source_path),
    }
    if not source.startswith(prompt):
        raise RuntimeError("constructed source is not prompt-prefixed")
    canonical_solution = source[len(prompt):]
    mbjp = {
        "task_id": record["task_id"],
        "language": "java",
        "prompt": prompt,
        "description": description,
        "test": test,
        "entry_point": task.method_name,
        "canonical_solution": canonical_solution,
        "metadata": {
            "source": "facebookresearch/TransCoder GFG Java evaluation",
            "source_file": task.source_path.name,
            "source_sha256": task.source_sha256,
            "normalized_method_sha256": task.normalized_method_sha256,
            "compatibility_modifications": task.compatibility_modifications,
            "group_id": task.group_id,
            "variant": task.variant,
            "difficulty": task.difficulty,
            "canonical_nonblank_loc": task.nonblank_loc,
            "fixed_test_cases": len(outputs),
            "license": "CC-BY-NC-4.0",
        },
    }
    return record, mbjp


def dump_json(value, path: Path) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def dump_jsonl(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcoder-root", type=Path, default=DEFAULT_TRANSCODER_ROOT)
    parser.add_argument("--reference-task", default=DEFAULT_REFERENCE_TASK)
    parser.add_argument("--output-root", type=Path, default=ROOT / "Utils" / "data")
    parser.add_argument("--date-tag", default="20260811")
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--compatibility-normalization", action="store_true")
    parser.add_argument(
        "--base-candidate-task",
        default="java_transcoder_gfg_candidates_t5gemma2_20260811",
        help="Keep already accepted tasks byte-for-byte unnormalized.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dir = args.transcoder_root / SOURCE_SUBDIR
    if not source_dir.is_dir():
        raise FileNotFoundError(f"TransCoder Java evaluation directory not found: {source_dir}")
    source_paths = sorted(source_dir.glob("*.java"))
    if args.limit:
        source_paths = source_paths[:args.limit]

    reference_dir = ROOT / "Utils" / "data" / args.reference_task
    tokenizer = load_pickle(reference_dir / "tokenizer.pkl")
    rules = load_pickle(reference_dir / "rules.pkl")
    program_model.tokenizer = tokenizer
    configure_runtime(rules, tokenizer)

    groups = compute_groups(source_paths)
    base_accepted: set[str] = set()
    if args.compatibility_normalization:
        base_mbjp = ROOT / "Utils" / "data" / args.base_candidate_task / "mbjp_format.jsonl"
        if not base_mbjp.is_file():
            raise FileNotFoundError(f"base candidate MBJP file not found: {base_mbjp}")
        with base_mbjp.open(encoding="utf-8") as handle:
            base_accepted = {json.loads(line)["task_id"] for line in handle if line.strip()}
    variants: dict[str, int] = {}
    extracted: list[ExtractedTask] = []
    preparation_report: list[dict] = []
    for path in source_paths:
        group = groups[path.stem]
        variant = variants.get(group, 0)
        variants[group] = variant + 1
        task_id = f"TransCoderGFG/{path.stem}"
        normalize_task = args.compatibility_normalization and task_id not in base_accepted
        try:
            task = build_extracted_task(
                path,
                variant,
                group,
                compatibility_normalization=normalize_task,
            )
            # Fail early on syntax/grammar incompatibility before running javac.
            tree = javalang.parse.parse(
                f"class {task.class_name} {{\n{task.canonical_method}\n}}"
            )
            java2impp.visit(tree).to_coq().tokenization()
            extracted.append(task)
            preparation_report.append(
                {
                    "source_file": path.name,
                    "task_id": f"TransCoderGFG/{path.stem}",
                    "status": "parser_accepted",
                    "group_id": group,
                    "variant": variant,
                    "difficulty": task.difficulty,
                    "canonical_nonblank_loc": task.nonblank_loc,
                    "compatibility_modifications": task.compatibility_modifications,
                }
            )
        except Exception as exc:
            preparation_report.append(
                {
                    "source_file": path.name,
                    "task_id": f"TransCoderGFG/{path.stem}",
                    "status": "parser_rejected",
                    "group_id": group,
                    "variant": variant,
                    "stage_error": f"{type(exc).__name__}: {exc}"[:1200],
                }
            )

    records: list[dict] = []
    mbjp_by_id: dict[str, dict] = {}

    def prepare(task: ExtractedTask):
        try:
            record, mbjp = make_record(task, args.timeout)
            return task, record, mbjp, None
        except Exception as exc:
            return task, None, None, f"{type(exc).__name__}: {exc}"[:1200]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        for index, (task, record, mbjp, error) in enumerate(
            executor.map(prepare, extracted), start=1
        ):
            status = next(
                item for item in preparation_report
                if item["source_file"] == task.source_path.name
            )
            if error:
                status["status"] = "fixed_test_failed"
                status["stage_error"] = error
            else:
                status["status"] = "fixed_test_ready"
                records.append(record)
                mbjp_by_id[record["task_id"]] = mbjp
            if index % 25 == 0 or index == len(extracted):
                print(
                    f"\rGFG preparation: {index}/{len(extracted)}, "
                    f"{len(records)} fixed tests ready",
                    end="",
                    flush=True,
                )
    print()

    kind = "compat_candidates" if args.compatibility_normalization else "candidates"
    dataset_name = f"java_transcoder_gfg_{kind}_t5gemma2_{args.date_tag}"
    checked, passed, destination = build_dataset(
        dataset_name,
        records,
        args.output_root,
        reference_dir,
        tokenizer,
        rules,
        args.timeout,
        args.workers,
    )

    conversion = json.loads((destination / "conversion_report.json").read_text())
    passed_ids = {
        row["task_id"] for row in conversion["rows"] if row["status"] == "passed"
    }
    accepted_mbjp = [
        mbjp_by_id[task_id] for task_id in sorted(passed_ids)
        if task_id in mbjp_by_id
    ]
    dump_jsonl(accepted_mbjp, destination / "mbjp_format.jsonl")
    plain_rows = [
        {
            "task_id": row["task_id"],
            "prompt": row["prompt"],
            "code": row["prompt"] + row["canonical_solution"],
            "test": row["test"],
            "type": "candidate",
            "benchmark": "transcoder_gfg",
            "original_split": "candidate_pool",
            "group_id": row["metadata"]["group_id"],
            "difficulty": row["metadata"]["difficulty"],
        }
        for row in accepted_mbjp
    ]
    dump_json(plain_rows, destination / "t5_plain_format.json")
    dump_json(
        {
            "dataset": dataset_name,
            "policy": "candidate pool only; no train/test split",
            "upstream": "https://github.com/facebookresearch/TransCoder",
            "upstream_commit": subprocess.run(
                ["git", "-C", str(args.transcoder_root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip(),
            "upstream_license": "CC-BY-NC-4.0",
            "compatibility_normalization": args.compatibility_normalization,
            "base_candidate_task": (
                args.base_candidate_task if args.compatibility_normalization else None
            ),
            "source_files": len(source_paths),
            "parser_accepted": sum(
                item["status"] != "parser_rejected" for item in preparation_report
            ),
            "fixed_test_ready": len(records),
            "full_roundtrip_accepted": len(accepted_mbjp),
            "groups": len({row["metadata"]["group_id"] for row in accepted_mbjp}),
            "difficulty": {
                level: sum(row["metadata"]["difficulty"] == level for row in accepted_mbjp)
                for level in ["easy", "medium", "hard"]
            },
        },
        destination / "candidate_manifest.json",
    )
    dump_json(preparation_report, destination / "preparation_report.json")

    # Keep the pool unusable as an accidental all-training split.  A later,
    # group-aware split builder must explicitly populate train/test.
    config_path = destination / "config.json"
    config = json.loads(config_path.read_text())
    config.update(
        {
            "candidate_pool_only": True,
            "evaluation_only": True,
            "train_test_split_required": True,
        }
    )
    dump_json(config, config_path)

    print(
        f"{destination}: parser accepted {len(extracted)}/{len(source_paths)}, "
        f"fixed tests {len(records)}, full round trip {passed}/{checked}"
    )


if __name__ == "__main__":
    main()
