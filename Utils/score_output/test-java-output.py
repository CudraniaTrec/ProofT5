import pickle, subprocess, argparse
from tqdm import trange, tqdm
import pandas as pd

output_mode = False
task_name = "mbjp"
test_type = "test"

output_dir = ""
dir_postfix= ""
test_codes = None   # test codes
prob_cnt = 0        # number of problems to test
pass_at_k = 10      # number of top k solutions to test

# load top k solutions and test codes
def load_data():
    global output_dir, test_codes, prob_cnt
    output_dir = f"../output/{task_name}_{test_type}_ans/"+dir_postfix
    test_codes = pickle.load(
        open(f"../data/{task_name}/{test_type}.pkl", "rb")
    )
    prob_cnt = len(test_codes)
    print(f"Total {prob_cnt} problems to test with {pass_at_k} passes")
    print(f"Output directory: {output_dir}")

# some solutions is ignored
def error_solution(code):
    if "IndexError" in code:
        return True
    if "GrammarError" in code:
        return False
    return False

def tests_one_problem(id):
    import os
    prefix = """import java.lang.*;
import java.util.*;
import java.io.*;
import java.math.*;
"""
    test_code = test_codes[id]["test"]
    compile_err_list, total_sol, success_list = [], 0, []
    for i in trange(pass_at_k, desc=f"Problem {id}"):
        file_name = f"{output_dir}{id}_{i}.java"
        if not os.path.exists(file_name):
            file_name = f"{output_dir}{id}_{i}.txt"
            if not os.path.exists(file_name):
                print(file_name)
                print(f"Problem {id} not found at time {i}")
                continue    
        with open(file_name, "r") as f:
            gen_code = f.read()
        if error_solution(gen_code):
            continue

        total_sol += 1
        full_code = f"{prefix}\n{gen_code}\n{test_code}"
        java_folder_path = f"forjava/tmp{id}"
        if not os.path.exists(java_folder_path):
            os.makedirs(java_folder_path)
        java_path=java_folder_path+"/Main.java"
        with open(java_path, "w") as f:
            f.write(full_code)
        try:
            res = subprocess.run(
                ["javac", "-d", java_folder_path, java_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=1,
            )
            if res.returncode == 0:  # compilation success
                res = subprocess.run(
                    ["java", "-cp", java_folder_path, "Main"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1,
                )
                if res.returncode == 0:  # run success
                    success_list.append(i)
                    print(f"Problem {id} success at time {i}")
                else:  # run failed
                    if output_mode:
                        print("=" * 50
                            + f"Runtime failed for problem {id} at time {i}"
                            + "=" * 50)
            else:  # compilation failed
                err = res.stderr.decode("unicode_escape")
                partial_code = f"{prefix}\n{gen_code}"
                with open(java_path, "w") as f:
                    f.write(partial_code)
                res = subprocess.run(
                    ["javac", "-d", java_folder_path, java_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1,
                )
                error_message = res.stderr.decode("unicode_escape")
                if ("missing return statement" in error_message or \
                    "unreachable statement" in error_message or \
                    "is already defined" in error_message or \
                    res.returncode == 0 or '?' in partial_code): #compiled w/o test codes
                    continue
                compile_err_list.append(i)
                # if output_mode:
                # print("=" * 50
                #     + f"Compilation failed for problem {id} at time {i}"
                #     + "=" * 50)
                # print(partial_code)
                # print(error_message)
        except subprocess.TimeoutExpired:
            if output_mode:
                print(
                    "\n" + "=" * 10 + f"Timeout for problem {id} at time {i}" + "=" * 10
                )
    # print(f"Problem {id} CE: {len(compile_err_list)}")
    return compile_err_list, total_sol, success_list

def main():
    success_cnt = 0 # number of problems solved
    compile_error_list = {} # compile error answers for each problem
    CE_rate_list = [] # compile error rate for each problem
    total_solutions = 0 # total number of solutions tested
    success_lists = [] # success answers for each problem
    problems_solved = [] # problems solved
    problems_CEed = [] # problems with compile errors
    reject_sampling_succ = 0 # number of problems solved by reject sampling
    reject_sampling_succ_10 = 0
    reject_sampling_rate = []

    import multiprocessing
    pool = multiprocessing.Pool(processes=32)
    results = pool.map(tests_one_problem, range(prob_cnt))
    pool.close()
    pool.join()

    for i in range(prob_cnt):
        compile_err, total_sol, success_list = results[i]
        compile_error_list[i] = compile_err
        total_solutions += total_sol
        success_lists.append(success_list)
        if total_sol == 0:
            CE_rate_list.append(1.1)
        else:
            CE_rate_list.append(len(compile_err) / total_sol)
        if len(success_list)>0:
            success_cnt += 1
            problems_solved.append(i)
            fst_succ_pos = success_list[0]
            if all(i in compile_err for i in range(fst_succ_pos)):
                reject_sampling_succ += 1
            # count all type correct candicate before fst_succ_pos
            type_corr_prog_before_fst = sum(1 for j in range(fst_succ_pos) if j not in compile_err)
            if type_corr_prog_before_fst <10:
                reject_sampling_succ_10 += 1
            reject_sampling_rate.append((i, fst_succ_pos, type_corr_prog_before_fst))
        if len(compile_err)>0:
            problems_CEed.append(i)

    # success rate, compile error rate
    success_rate = success_cnt / prob_cnt
    compile_err_cnt = sum([len(compile_error_list[i]) for i in compile_error_list])
    CE_rate = compile_err_cnt / total_solutions
    # first success position, average success rate, first success count
    first_success_pos = [(succ_list[0] if len(succ_list) > 0 else pass_at_k) for succ_list in success_lists]
    avg_first_success_pos = sum(first_success_pos) / len(first_success_pos)
    avg_success_rate = sum(len(succ_list) for succ_list in success_lists) / total_solutions
    first_success_cnt = sum(1 for pos in first_success_pos if pos == 0)
    

    # print results
    success_rate = f"{success_rate*100:.2f}%"
    CE_rate = f"{CE_rate*100:.2f}%"
    avg_first_success_pos = f"{avg_first_success_pos:.2f}"
    avg_success_rate = f"{avg_success_rate*100:.2f}%"
    print(f"Success rate: {success_rate}: {success_cnt}/{prob_cnt}")
    print(f"Compilation error rate: {CE_rate}: {compile_err_cnt}/{total_solutions}")
    print(f"avg first success position: {avg_first_success_pos}")
    print(f"avg success rate: {avg_success_rate}")
    print(f"first success count: {first_success_cnt}")
    print(f"Reject sampling success: {reject_sampling_succ} ({(reject_sampling_succ/prob_cnt)*100:.2f}%)")
    print(f"Reject sampling success with 10 type correct candidates: {reject_sampling_succ_10} ({(reject_sampling_succ_10/prob_cnt)*100:.2f}%)")
    for idx, pos, type_corr in reject_sampling_rate:
        if pos < pass_at_k:
            print(f"Reject sampling {idx} success at position {pos} with \t{type_corr} type correct before")

    import json
    with open("compile_error_list.json", "w") as f:
        json.dump(compile_error_list, f, indent=4)
    results = pd.read_csv('result.csv',index_col="name")
    res_row_name = f"{task_name}__{test_type}"
    if dir_postfix:
        res_row_name += f"({dir_postfix[:-1]})"
    results.loc[res_row_name, :] = [success_rate, success_cnt, prob_cnt, str(problems_solved), 
                                    CE_rate, compile_err_cnt, total_solutions, str(problems_CEed), str(CE_rate_list),
                                    str(first_success_pos), avg_first_success_pos, 
                                    avg_success_rate, first_success_cnt, f"{(first_success_cnt/prob_cnt)*100:.2f}%"]
    results.to_csv('result.csv', index=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test MBJP model output")
    parser.add_argument(
        "--output", action="store_true", help="Whether to output the error message"
    )
    parser.add_argument(
        "--task", type=str, default="mbjp", help="Which task to test(default: mbjp)"
    )
    parser.add_argument(
        "--valid",
        action="store_true",
        help="Whether to test on validation set (default: test set)",
    )
    parser.add_argument(
        "--train", 
        action="store_true",
        help="Whether to test on training set (default: test set)",
    )
    parser.add_argument(
        "--test", 
        action="store_true",
        help="Whether to test on test set (default: test set)",
    )
    parser.add_argument(
        "--train_time",
        type=str,
        default="",
        help="The time to test on training set (default: all)",
    )
    parser.add_argument(
        "--checkpoint_epoch",
        type=str,
        default="100",
        help="The epoch of checkpoint to test (default: 200)",
    )
    
    argc = parser.parse_args()
    output_mode = argc.output
    test_type = "valid" if argc.valid else "train" if argc.train else "test"
    task_name = argc.task
    if argc.train_time:
        dir_postfix = f"{argc.train_time}/{argc.checkpoint_epoch}/"
    load_data()
    main()
    # tests_one_problem(74)
