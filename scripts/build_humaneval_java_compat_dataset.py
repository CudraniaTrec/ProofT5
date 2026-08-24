#!/usr/bin/env python3
"""Build a compatibility-normalized, MBJP-shaped HumanEval-Java pool."""

from __future__ import annotations

import argparse
import json
import pickle
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "coq_model"))

import myjavalang as javalang  # noqa: E402
import program_model  # noqa: E402
from beamsearch_coq import configure_runtime  # noqa: E402
from scripts.build_java_external_datasets import (  # noqa: E402
    DEFAULT_REFERENCE_TASK,
    build_dataset,
    load_pickle,
)
from scripts.build_transcoder_gfg_java_dataset import matching_delimiter  # noqa: E402


BASE_TASK = "java_humaneval_external_t5gemma2_20260730"


METHOD_OVERRIDES: dict[int, str] = {
    26: """public List<Integer> removeDuplicates(List<Integer> numbers) {
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < numbers.size(); i++) {
            int value = numbers.get(i);
            int count = 0;
            for (int j = 0; j < numbers.size(); j++) {
                int other = numbers.get(j);
                if (value == other) count++;
            }
            if (count == 1) result.add(value);
        }
        return result;
    }""",
    29: """public List<String> filterByPrefix(List<String> strings, String prefix) {
        List<String> result = new ArrayList<>();
        for (String value : strings) {
            if (value.startsWith(prefix)) result.add(value);
        }
        return result;
    }""",
    30: """public List<Integer> getPositive(List<Integer> l) {
        List<Integer> result = new ArrayList<>();
        for (int value : l) if (value > 0) result.add(value);
        return result;
    }""",
    42: """public List<Integer> incrList(List<Integer> l) {
        List<Integer> result = new ArrayList<>();
        for (int value : l) result.add(value + 1);
        return result;
    }""",
    67: """public int fruitDistribution(String s, int n) {
        int used = 0;
        String[] parts = s.split(" ");
        for (String part : parts) {
            boolean numeric = part.length() > 0;
            int value = 0;
            for (int i = 0; i < part.length(); i++) {
                char ch = part.charAt(i);
                if (ch < '0' || ch > '9') numeric = false;
                else value = value * 10 + ch - '0';
            }
            if (numeric) used += value;
        }
        return n - used;
    }""",
    72: """public boolean willItFly(List<Integer> q, int w) {
        int sum = 0;
        for (int value : q) sum += value;
        if (sum > w) return false;
        int i = 0;
        int j = q.size() - 1;
        while (i < j) {
            int left = q.get(i);
            int right = q.get(j);
            if (left != right) return false;
            i++;
            j--;
        }
        return true;
    }""",
    75: """public boolean isMultiplyPrime(int a) {
        for (int i = 2; i < 101; i++) {
            boolean primeI = true;
            for (int d = 2; d < i; d++) if (i % d == 0) primeI = false;
            if (!primeI) continue;
            for (int j = i; j < 101; j++) {
                boolean primeJ = true;
                for (int d = 2; d < j; d++) if (j % d == 0) primeJ = false;
                if (!primeJ) continue;
                for (int k = j; k < 101; k++) {
                    boolean primeK = true;
                    for (int d = 2; d < k; d++) if (k % d == 0) primeK = false;
                    if (primeK && i * j * k == a) return true;
                }
            }
        }
        return false;
    }""",
    91: """public int isBored(String S) {
        int count = 0;
        boolean atStart = true;
        for (int i = 0; i < S.length(); i++) {
            char ch = S.charAt(i);
            if (ch == '.' || ch == '?' || ch == '!') {
                atStart = true;
            } else if (atStart && ch == ' ') {
                continue;
            } else if (atStart) {
                if (ch == 'I' && i + 1 < S.length() && S.charAt(i + 1) == ' ') count++;
                atStart = false;
            }
        }
        return count;
    }""",
    95: """public boolean checkDictCase(Map<Object, Object> dict) {
        if (dict.isEmpty()) return false;
        int mode = 0;
        for (Object objectKey : dict.keySet()) {
            if (objectKey instanceof String) { mode += 0; }
            else return false;
            String key = (String) objectKey;
            boolean upper = true;
            boolean lower = true;
            for (int i = 0; i < key.length(); i++) {
                char ch = key.charAt(i);
                if (ch >= 'a' && ch <= 'z') upper = false;
                else if (ch >= 'A' && ch <= 'Z') lower = false;
                else { upper = false; lower = false; }
            }
            if (!upper && !lower) return false;
            int current = upper ? 1 : 2;
            if (mode == 0) mode = current;
            else if (mode != current) return false;
        }
        return true;
    }""",
    99: """public int countUpper(String value) {
        boolean negative = value.charAt(0) == '-';
        int start = negative ? 1 : 0;
        int whole = 0;
        int fraction = 0;
        for (int i = start; i < value.length(); i++) {
            char ch = value.charAt(i);
            if (ch == '.') {
                if (i + 1 < value.length()) fraction = value.charAt(i + 1) - '0';
                break;
            }
            whole = whole * 10 + ch - '0';
        }
        if (fraction >= 5) whole++;
        return negative ? -whole : whole;
    }""",
    101: """public List<String> wordStrings(String s) {
        List<String> result = new ArrayList<>();
        String word = "";
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            if (ch == ',' || ch == ' ') {
                if (word.length() > 0) { result.add(word); word = ""; }
            } else word += ch;
        }
        if (word.length() > 0) result.add(word);
        return result;
    }""",
    108: """public int countNums(List<Integer> arr) {
        int result = 0;
        for (int original : arr) {
            int value = Math.abs(original);
            String digits = String.valueOf(value);
            int sum = 0;
            for (int i = 0; i < digits.length(); i++) {
                int digit = digits.charAt(i) - '0';
                if (original < 0 && i == 0) sum -= digit;
                else sum += digit;
            }
            if (sum > 0) result++;
        }
        return result;
    }""",
    115: """public int maxFill(List<List<Integer>> grid, int capacity) {
        int result = 0;
        for (List<Integer> row : grid) {
            int water = 0;
            for (int value : row) water += value;
            result += (water + capacity - 1) / capacity;
        }
        return result;
    }""",
    116: """public List<Integer> sortArray(List<Integer> arr) {
        List<Integer> result = new ArrayList<>(arr);
        for (int i = 0; i < result.size(); i++) {
            for (int j = i + 1; j < result.size(); j++) {
                int left = result.get(i);
                int right = result.get(j);
                int a = Math.abs(left);
                int b = Math.abs(right);
                int bitsA = 0;
                int bitsB = 0;
                while (a > 0) { bitsA += a % 2; a /= 2; }
                while (b > 0) { bitsB += b % 2; b /= 2; }
                if (bitsA > bitsB || (bitsA == bitsB && left > right)) {
                    result.set(i, right);
                    result.set(j, left);
                }
            }
        }
        return result;
    }""",
    122: """public int addElements(List<Integer> arr, int k) {
        int result = 0;
        for (int i = 0; i < k; i++) {
            int value = arr.get(i);
            if (Math.abs(value) <= 99) result += value;
        }
        return result;
    }""",
    124: """public boolean validDate(String date) {
        date = date.trim();
        String[] parts = date.split("-");
        if (parts.length != 3) return false;
        int[] values = new int[3];
        for (int i = 0; i < 3; i++) {
            if (parts[i].length() == 0) return false;
            for (int j = 0; j < parts[i].length(); j++) {
                char ch = parts[i].charAt(j);
                if (ch < '0' || ch > '9') return false;
                values[i] = values[i] * 10 + ch - '0';
            }
        }
        int month = values[0];
        int day = values[1];
        if (month < 1 || month > 12 || day < 1) return false;
        if (month == 2) return day <= 29;
        if (month == 4 || month == 6 || month == 9 || month == 11) return day <= 30;
        return day <= 31;
    }""",
    125: """public Object splitWords(String txt) {
        if (txt.contains(" ") || txt.contains(",")) {
            List<String> result = new ArrayList<>();
            String word = "";
            boolean splitOnSpace = txt.contains(" ");
            for (int i = 0; i < txt.length(); i++) {
                char ch = txt.charAt(i);
                if ((splitOnSpace && ch == ' ') || (!splitOnSpace && ch == ',')) {
                    if (word.length() > 0) { result.add(word); word = ""; }
                } else word += ch;
            }
            if (word.length() > 0) result.add(word);
            return result;
        }
        int count = 0;
        for (int i = 0; i < txt.length(); i++) {
            char ch = txt.charAt(i);
            if (ch >= 'a' && ch <= 'z' && (ch - 'a') % 2 == 1) count++;
        }
        return count;
    }""",
    128: """public Optional<Integer> prodSigns(List<Integer> arr) {
        if (arr.size() == 0) return Optional.empty();
        int negatives = 0;
        int sum = 0;
        for (int value : arr) {
            if (value == 0) return Optional.of(0);
            if (value < 0) negatives++;
            sum += Math.abs(value);
        }
        return Optional.of((negatives % 2 == 0 ? 1 : -1) * sum);
    }""",
    133: """public int sumSquares(List<Double> lst) {
        int result = 0;
        for (double value : lst) {
            int rounded = (int) Math.ceil(value);
            result += rounded * rounded;
        }
        return result;
    }""",
    134: """public boolean checkIfLastCharIsALetter(String txt) {
        int lastSpace = -1;
        for (int i = 0; i < txt.length(); i++) if (txt.charAt(i) == ' ') lastSpace = i;
        String check = txt.substring(lastSpace + 1);
        if (check.length() != 1) return false;
        char ch = check.charAt(0);
        return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z');
    }""",
    136: """public List<Optional<Integer>> largestSmallestIntegers(List<Integer> lst) {
        boolean hasNegative = false;
        boolean hasPositive = false;
        int negativeValue = 0;
        int positiveValue = 0;
        for (int value : lst) {
            if (value < 0 && (!hasNegative || value > negativeValue)) { hasNegative = true; negativeValue = value; }
            if (value > 0 && (!hasPositive || value < positiveValue)) { hasPositive = true; positiveValue = value; }
        }
        List<Optional<Integer>> result = new ArrayList<>();
        if (hasNegative) result.add(Optional.of(negativeValue));
        else result.add(Optional.empty());
        if (hasPositive) result.add(Optional.of(positiveValue));
        else result.add(Optional.empty());
        return result;
    }""",
    137: """public Optional<Object> compareOne(Object a, Object b) {
        String first = a.toString().replace(',', '.');
        String second = b.toString().replace(',', '.');
        int firstScaled = 0;
        int secondScaled = 0;
        boolean firstDecimal = false;
        boolean secondDecimal = false;
        for (int i = 0; i < first.length(); i++) {
            char ch = first.charAt(i);
            if (ch == '.') firstDecimal = true;
            else if (!firstDecimal) firstScaled = firstScaled * 10 + ch - '0';
            else { firstScaled = firstScaled * 10 + ch - '0'; break; }
        }
        if (!firstDecimal) firstScaled *= 10;
        for (int i = 0; i < second.length(); i++) {
            char ch = second.charAt(i);
            if (ch == '.') secondDecimal = true;
            else if (!secondDecimal) secondScaled = secondScaled * 10 + ch - '0';
            else { secondScaled = secondScaled * 10 + ch - '0'; break; }
        }
        if (!secondDecimal) secondScaled *= 10;
        if (firstScaled == secondScaled) return Optional.empty();
        if (firstScaled > secondScaled) return Optional.of(a);
        return Optional.of(b);
    }""",
    139: """public double specialFactorial(int n) {
        double factorial = 1.0;
        double result = 1.0;
        for (int i = 1; i <= n; i++) {
            factorial *= i;
            result *= factorial;
        }
        return result;
    }""",
    141: """public String filenameCheck(String file_name) {
        int dot = -1;
        int dots = 0;
        for (int i = 0; i < file_name.length(); i++) {
            if (file_name.charAt(i) == '.') { dot = i; dots++; }
        }
        if (dots != 1 || dot == 0) return "No";
        String base = file_name.substring(0, dot);
        String suffix = file_name.substring(dot + 1);
        if (!suffix.equals("txt") && !suffix.equals("exe") && !suffix.equals("dll")) return "No";
        char first = base.charAt(0);
        int digits = 0;
        boolean startsWithLetter = (first >= 'a' && first <= 'z') || (first >= 'A' && first <= 'Z');
        if (startsWithLetter) { digits += 0; }
        else return "No";
        for (int i = 0; i < base.length(); i++) {
            char ch = base.charAt(i);
            if (ch >= '0' && ch <= '9') digits++;
        }
        return digits <= 3 ? "Yes" : "No";
    }""",
    142: """public int sumSquares(List<Integer> lst) {
        int result = 0;
        for (int i = 0; i < lst.size(); i++) {
            int value = lst.get(i);
            if (i % 3 == 0) result += value * value;
            else if (i % 4 == 0) result += value * value * value;
            else result += value;
        }
        return result;
    }""",
    145: """public List<Integer> orderByPoints(List<Integer> nums) {
        List<Integer> result = new ArrayList<>(nums);
        List<Integer> scores = new ArrayList<>();
        for (int value : result) {
            int absolute = Math.abs(value);
            int remaining = absolute;
            int score = 0;
            while (remaining > 0) { score += remaining % 10; remaining /= 10; }
            if (value < 0) {
                int divisor = 1;
                while (absolute / divisor >= 10) divisor *= 10;
                score -= 2 * (absolute / divisor);
            }
            scores.add(score);
        }
        for (int i = 1; i < result.size(); i++) {
            int key = result.get(i);
            int keySum = scores.get(i);
            int j = i - 1;
            while (j >= 0 && scores.get(j) > keySum) {
                result.set(j + 1, result.get(j));
                scores.set(j + 1, scores.get(j));
                j--;
            }
            result.set(j + 1, key);
            scores.set(j + 1, keySum);
        }
        return result;
    }""",
    148: """public List<String> bf(String planet1, String planet2) {
        int first = -1;
        int second = -1;
        if (planet1.equals("Mercury")) first = 0; else if (planet1.equals("Venus")) first = 1; else if (planet1.equals("Earth")) first = 2; else if (planet1.equals("Mars")) first = 3; else if (planet1.equals("Jupiter")) first = 4; else if (planet1.equals("Saturn")) first = 5; else if (planet1.equals("Uranus")) first = 6; else if (planet1.equals("Neptune")) first = 7;
        if (planet2.equals("Mercury")) second = 0; else if (planet2.equals("Venus")) second = 1; else if (planet2.equals("Earth")) second = 2; else if (planet2.equals("Mars")) second = 3; else if (planet2.equals("Jupiter")) second = 4; else if (planet2.equals("Saturn")) second = 5; else if (planet2.equals("Uranus")) second = 6; else if (planet2.equals("Neptune")) second = 7;
        List<String> result = new ArrayList<>();
        if (first < 0 || second < 0 || first == second) return result;
        int low = Math.min(first, second);
        int high = Math.max(first, second);
        for (int i = low + 1; i < high; i++) {
            if (i == 1) result.add("Venus"); else if (i == 2) result.add("Earth"); else if (i == 3) result.add("Mars"); else if (i == 4) result.add("Jupiter"); else if (i == 5) result.add("Saturn"); else if (i == 6) result.add("Uranus");
        }
        return result;
    }""",
    149: """public List<String> listSort(List<String> lst) {
        List<String> filtered = new ArrayList<>();
        for (String value : lst) if (value.length() % 2 == 0) filtered.add(value);
        Collections.sort(filtered);
        for (int i = 1; i < filtered.size(); i++) {
            String key = filtered.get(i);
            int j = i - 1;
            while (j >= 0 && filtered.get(j).length() > key.length()) {
                filtered.set(j + 1, filtered.get(j));
                j--;
            }
            filtered.set(j + 1, key);
        }
        return filtered;
    }""",
    151: """public int doubleTheDifference(List<Object> lst) {
        int result = 0;
        for (Object item : lst) {
            if (item instanceof Integer) {
                int value = (Integer) item;
                if (value > 0 && value % 2 != 0) result += value * value;
            }
        }
        return result;
    }""",
    153: """public String StrongestExtension(String class_name, List<String> extensions) {
        String best = extensions.get(0);
        int bestScore = -1000000;
        for (String extension : extensions) {
            int score = 0;
            for (int i = 0; i < extension.length(); i++) {
                char ch = extension.charAt(i);
                if (ch >= 'A' && ch <= 'Z') score++;
                else if (ch >= 'a' && ch <= 'z') score--;
            }
            if (score > bestScore) { best = extension; bestScore = score; }
        }
        return class_name + "." + best;
    }""",
    156: """public String intToMiniRoman(int number) {
        String result = "";
        while (number >= 1000) { result += "M"; number -= 1000; }
        while (number >= 900) { result += "CM"; number -= 900; }
        while (number >= 500) { result += "D"; number -= 500; }
        while (number >= 400) { result += "CD"; number -= 400; }
        while (number >= 100) { result += "C"; number -= 100; }
        while (number >= 90) { result += "XC"; number -= 90; }
        while (number >= 50) { result += "L"; number -= 50; }
        while (number >= 40) { result += "XL"; number -= 40; }
        while (number >= 10) { result += "X"; number -= 10; }
        while (number >= 9) { result += "IX"; number -= 9; }
        while (number >= 5) { result += "V"; number -= 5; }
        while (number >= 4) { result += "IV"; number -= 4; }
        while (number >= 1) { result += "I"; number -= 1; }
        return result.toLowerCase();
    }""",
    158: """public String findMax(List<String> words) {
        String best = words.get(0);
        int bestUnique = -1;
        for (String word : words) {
            int unique = 0;
            for (int i = 0; i < word.length(); i++) {
                boolean first = true;
                for (int j = 0; j < i; j++) if (word.charAt(i) == word.charAt(j)) first = false;
                if (first) unique++;
            }
            boolean smaller = false;
            if (unique == bestUnique) {
                int common = Math.min(word.length(), best.length());
                for (int i = 0; i < common; i++) {
                    if (word.charAt(i) < best.charAt(i)) { smaller = true; break; }
                    if (word.charAt(i) > best.charAt(i)) break;
                }
                if (word.length() < best.length() && word.substring(0, common).equals(best.substring(0, common))) smaller = true;
            }
            if (unique > bestUnique || smaller) { best = word; bestUnique = unique; }
        }
        return best;
    }""",
}


def replace_primary_method(source: str, replacement: str) -> str:
    class_open = source.find("{", source.find("class Solution"))
    method = re.search(r"\bpublic\s+[^;{}]+\([^;{}]*\)\s*(?:throws\s+[^{}]+)?\{", source[class_open + 1:])
    if method is None:
        raise ValueError("primary HumanEval method not found")
    start = class_open + 1 + method.start()
    opening = source.find("{", start)
    closing = matching_delimiter(source, opening, "{", "}")
    return source[:start] + replacement + source[closing + 1:]


def description_from_prompt(prompt: str) -> str:
    match = re.search(r"/\*\*(.*?)\*/", prompt, flags=re.S)
    if match is None:
        raise ValueError("HumanEval prompt has no Javadoc description")
    lines = []
    for raw in match.group(1).splitlines():
        line = re.sub(r"^\s*\*?\s?", "", raw).strip()
        if not line:
            if lines:
                break
            continue
        if line.startswith(">>>") or line.lower().startswith(("example", "for example")):
            break
        lines.append(line)
    return " ".join(lines).strip()


def entry_point_from_prompt(prompt: str) -> str:
    matches = re.findall(
        r"\b(?:public|private|protected)\s+(?:static\s+)?"
        r"(?:<[^>]+>\s+)?[\w<>,\[\] ?]+\s+([A-Za-z_$][\w$]*)\s*\(",
        prompt,
    )
    if not matches:
        raise ValueError("HumanEval prompt method signature not found")
    return matches[-1]


def mbjp_canonical_solution(source: str, entry_point: str) -> str:
    class_match = re.search(r"\bclass\s+Solution\s*\{", source)
    if class_match is None:
        raise ValueError("HumanEval Solution class not found")
    class_open = source.find("{", class_match.start())
    class_close = matching_delimiter(source, class_open, "{", "}")
    method_pattern = re.compile(
        r"\b(?:public|private|protected)\s+(?:static\s+)?"
        r"(?:<[^>]+>\s+)?[\w<>,\[\] ?]+\s+"
        + re.escape(entry_point)
        + r"\s*\([^;{}]*\)\s*(?:throws\s+[^{}]+)?\{"
    )
    method = method_pattern.search(source, class_open + 1, class_close)
    if method is None:
        raise ValueError(f"source method {entry_point!r} not found")
    opening = source.find("{", method.start())
    closing = matching_delimiter(source, opening, "{", "}")
    target_body_and_close = source[opening + 1:closing + 1]
    # HumanEval prompts already include any helper members that precede the
    # target signature. Appending them again would duplicate the methods.
    return target_body_and_close.rstrip() + "\n}"


def dump_json(value, path: Path) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date-tag", default="20260811")
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--reference-task", default=DEFAULT_REFERENCE_TASK)
    parser.add_argument("--output-root", type=Path, default=ROOT / "Utils" / "data")
    args = parser.parse_args()

    metadata = json.loads((ROOT / "coq_model" / "datas" / "humaneval.json").read_text())
    by_number = {int(row["task_id"].split("/")[-1]): row for row in metadata}
    base_dir = ROOT / "Utils" / "data" / BASE_TASK
    with (base_dir / "test.pkl").open("rb") as handle:
        base_rows = pickle.load(handle)
    base_ids = {row["task_id"] for row in base_rows}

    reference_dir = ROOT / "Utils" / "data" / args.reference_task
    tokenizer = load_pickle(reference_dir / "tokenizer.pkl")
    rules = load_pickle(reference_dir / "rules.pkl")
    program_model.tokenizer = tokenizer
    configure_runtime(rules, tokenizer)

    records = []
    mbjp_by_id = {}
    for number in sorted(by_number):
        row = by_number[number]
        task_id = f"HumanEval-Java/{number}"
        source_path = ROOT / "coq_model" / "datas" / "humaneval" / f"Java_{number}.java"
        source = source_path.read_text()
        modifications: list[str] = []
        if task_id not in base_ids and number in METHOD_OVERRIDES:
            source = replace_primary_method(source, METHOD_OVERRIDES[number])
            modifications.append(f"explicit_loop_rewrite:{number}")
        prompt = row["prompt"]
        if number == 139 and modifications:
            prompt = prompt.replace(
                "public long specialFactorial(int n)",
                "public double specialFactorial(int n)",
            )
        entry_point = entry_point_from_prompt(prompt)
        description = description_from_prompt(prompt)
        record = {
            "task_id": task_id,
            "prompt": prompt,
            "description": description,
            "source": source,
            "test": row["test"],
            "source_file": str(source_path.relative_to(ROOT)),
        }
        records.append(record)
        canonical_solution = mbjp_canonical_solution(source, entry_point)
        mbjp_by_id[task_id] = {
            "task_id": task_id,
            "language": "java",
            "prompt": prompt,
            "description": description,
            "test": row["test"],
            "entry_point": entry_point,
            "canonical_solution": canonical_solution,
            "metadata": {
                "source": "HumanEval Java",
                "source_file": source_path.name,
                "original_task_id": row["task_id"],
                "compatibility_modifications": modifications,
            },
        }

    name = f"java_humaneval_compat_candidates_t5gemma2_{args.date_tag}"
    checked, passed, destination = build_dataset(
        name, records, args.output_root, reference_dir, tokenizer, rules, args.timeout, args.workers
    )
    report = json.loads((destination / "conversion_report.json").read_text())
    accepted_ids = {item["task_id"] for item in report["rows"] if item["status"] == "passed"}
    accepted = [mbjp_by_id[task_id] for task_id in sorted(accepted_ids)]
    with (destination / "mbjp_format.jsonl").open("w", encoding="utf-8") as handle:
        for row in accepted:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    plain = [
        {
            "task_id": row["task_id"],
            "prompt": row["prompt"],
            "code": row["prompt"] + row["canonical_solution"],
            "test": row["test"],
            "type": "candidate",
            "benchmark": "humaneval_java",
            "original_split": "candidate_pool",
        }
        for row in accepted
    ]
    dump_json(plain, destination / "t5_plain_format.json")
    dump_json(
        {
            "dataset": name,
            "policy": "candidate pool only; no train/test split",
            "source_tasks": len(records),
            "base_accepted": len(base_ids),
            "full_roundtrip_accepted": len(accepted),
            "newly_recovered": len(accepted_ids - base_ids),
            "all_base_preserved": base_ids <= accepted_ids,
        },
        destination / "candidate_manifest.json",
    )
    config_path = destination / "config.json"
    config = json.loads(config_path.read_text())
    config.update({"candidate_pool_only": True, "evaluation_only": True, "train_test_split_required": True})
    dump_json(config, config_path)
    print(f"{destination}: {passed}/{checked} full-roundtrip tasks")


if __name__ == "__main__":
    main()
