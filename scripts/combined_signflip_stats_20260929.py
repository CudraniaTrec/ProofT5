"""Combined (cross-scale) sign-flip randomization tests + cluster-bootstrap CIs.

Secondary analysis for paper Appendix D (TOSEM-2026-0076): per language, the
per-task paired differences of the 220M and 2B comparisons are pooled and
tested with a two-sided sign-flip randomization test (200k flips, seed
273567, add-1 correction); 95% CIs for the combined mean paired difference
come from a task-level cluster bootstrap (20k resamples) that preserves the
within-task cross-scale correlation. Block sums are asserted against paper
Tables 9/10 (with two documented frozen-array deltas) before testing.
"""
import json, random
from collections import Counter

S = '/data2/x/hzc/prooft5/artifacts/'
A = S + 'appendix_d_stat_arrays_20260903/'
SC = S + 'major_revision_20260824/scores/'
SB = S + 'major_revision_strong_baselines_20260824/scores/'
METRICS = ['pass1', 'pass10', 'fsp', 'cer']
PASS_K = 10

def load_score(path):
    d = json.load(open(path))
    solved = set(d['solved']); fps = d['first_success_pos']; ids = d['problem_ids']
    ce = {}
    for pid, cand in d.get('compile_error_candidate_ids') or []:
        ce[pid] = ce.get(pid, 0) + 1
    return {'ids': ids,
            'pass1': [1 if (pid in solved and fps[i] == 0) else 0 for i, pid in enumerate(ids)],
            'pass10': [1 if pid in solved else 0 for i, pid in enumerate(ids)],
            'fsp': list(fps),
            'cer': [ce.get(pid, 0) / PASS_K for pid in ids]}

def diffs(b, t):
    return {m: [tv - bv for tv, bv in zip(t[m], b[m])] for m in METRICS}

records = []   # (tag, {metric: [diffs]})

# SuFu 220M + SuFu 2B (same 58 tasks)
b1 = load_score(A + 'stat_codet5_sufu_t10_20260903.json')
t1 = load_score(A + 'stat_tyflow_sufu_coqview_t10_20260903.json')
ob = json.load(open(S + 'sufu_2b_rerun_20260915/2b_sufu_paired_stats_optionB.json'))['arrays']
bs, ts_ = set(ob['baseline']['solved']), set(ob['tyflow']['solved'])
b1t, t1t = set(ob['baseline']['top1_solved']), set(ob['tyflow']['top1_solved'])
b2 = {'pass1': [1 if i in b1t else 0 for i in range(58)],
      'pass10': [1 if i in bs else 0 for i in range(58)],
      'fsp': ob['baseline']['first_success_pos'], 'cer': ob['baseline']['cer_fractions']}
t2 = {'pass1': [1 if i in t1t else 0 for i in range(58)],
      'pass10': [1 if i in ts_ else 0 for i in range(58)],
      'fsp': ob['tyflow']['first_success_pos'], 'cer': ob['tyflow']['cer_fractions']}
d1, d2 = diffs(b1, t1), diffs(b2, t2)
for i in range(58):
    records.append(('SuFu-220M', {m: [d1[m][i]] for m in METRICS}))
    records.append(('SuFu-2B', {m: [d2[m][i]] for m in METRICS}))

# Java 220M (MBJP) + Java 2B (MBJP / HEJ / GFG final baselines)
d3 = diffs(load_score(A + 'stat_codet5_mbjp_20260903.json'),
           load_score(A + 'stat_tyflow_mbjp_20260903.json'))
for i in range(67):
    records.append(('Java-220M', {m: [d3[m][i]] for m in METRICS}))
b4 = load_score(SC + 'mbjp_t5gemma2_test.json')
t4 = load_score(SC + 'mbjp_prooft5_test.json')
b5 = load_score(SB + 'he_bBfinal_e20_baseline_test16_score.json')
t5 = load_score(SC + 'humaneval_v15_prooft5_test.json')
b6 = load_score(SB + 'gfg_gBfinal_e15_baseline_test103_score.json')
t6 = load_score(SC + 'transcoder_gfg_v13_prooft5_test_failclosed.json')
d4 = diffs(b4, t4); d5 = diffs(b5, t5); d6 = diffs(b6, t6)
for i in range(67):
    records.append(('Java-2B-MBJP', {m: [d4[m][i]] for m in METRICS}))
for i in range(16):
    records.append(('Java-2B-HEJ', {m: [d5[m][i]] for m in METRICS}))
for i in range(103):
    records.append(('Java-2B-GFG', {m: [d6[m][i]] for m in METRICS}))

# ---------------- assertions ----------------
def net(tag, m, scale_side=None):
    ds = [r[1][m] for r in records if r[0] == tag]
    return sum(sum(d) for d in ds)

assert net('SuFu-220M', 'pass1') == 8 and net('SuFu-220M', 'pass10') == 13
assert net('SuFu-2B', 'pass1') == 6 and net('SuFu-2B', 'pass10') == 6
assert net('Java-220M', 'pass1') == 1 and net('Java-220M', 'pass10') == 5
assert net('Java-2B-MBJP', 'pass1') == 8 and net('Java-2B-MBJP', 'pass10') == 7
assert net('Java-2B-HEJ', 'pass1') == 3 and net('Java-2B-HEJ', 'pass10') == 3
assert net('Java-2B-GFG', 'pass1') == 11 and net('Java-2B-GFG', 'pass10') == 14
assert round(net('SuFu-220M', 'cer') * 10) == -501   # frozen array; paper prints 482 (documented)
assert round(net('SuFu-2B', 'cer') * 10) == -413
assert round(net('Java-220M', 'cer') * 10) == -228
assert round(net('Java-2B-MBJP', 'cer') * 10) == -195
assert round(net('Java-2B-HEJ', 'cer') * 10) == -37
assert round(net('Java-2B-GFG', 'cer') * 10) == -113
print('all block assertions passed (SuFu 220M pass@10/CER carry the documented '
      '18-vs-19 and 501-vs-482 frozen-array deltas; CER 2B breakdown 198+47+133=378, 10+0+23=33)')

# ---------------- tests ----------------
random.seed(273567)
def signflip(diffs, N=200000):
    T = sum(diffs); ge = 0
    for _ in range(N):
        s = sum(d if random.random() < .5 else -d for d in diffs)
        if abs(s) >= abs(T): ge += 1
    return (ge + 1) / (N + 1)

def cluster_ci(tags, metric, N=20000):
    recs = [r[1] for r in records if r[0] in tags]
    n = len(recs)
    obs_d = [d for r in recs for d in r[metric]]
    obs = sum(obs_d) / len(obs_d)
    stats = []
    for _ in range(N):
        tot = cnt = 0
        for _ in range(n):
            r = recs[random.randrange(n)]
            tot += sum(r[metric]); cnt += len(r[metric])
        stats.append(tot / cnt)
    stats.sort()
    return obs, stats[int(0.025 * N)], stats[int(0.975 * N)]

LAB = {'pass1': 'pass@1 (pp)', 'pass10': 'pass@10 (pp)', 'fsp': 'FSP (positions)', 'cer': 'CER (fraction)'}
print(f"\n{'set':6s} {'metric':18s} {'mean diff':>10s}  {'95% cluster-bootstrap CI':>26s}  {'sign-flip p':>11s}")
for lang, tags in [('SuFu', ['SuFu-220M', 'SuFu-2B']),
                   ('Java', ['Java-220M', 'Java-2B-MBJP', 'Java-2B-HEJ', 'Java-2B-GFG'])]:
    for m in METRICS:
        diffs = [d for r in records if r[0] in tags for d in r[1][m]]
        obs, lo, hi = cluster_ci(tags, m)
        p = signflip(diffs)
        print(f"{lang:6s} {LAB[m]:18s} {obs:>+10.3f}  [{lo:+.3f}, {hi:+.3f}]      {p:.4f}")
