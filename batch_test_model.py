import os, subprocess, re, datetime, json

def batch_test_model(task_name, gpus=8, epochs=range(-1, 201, 20), train_time = "", generate=True):
    # get train_time
    if train_time == "":
        if generate:
            model_path = f"Utils/models/Model{task_name}"
            dirs = os.listdir(model_path)
            date_pattern = r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$'
            date_dirs = []
            for dir in dirs:
                full_path = os.path.join(model_path, dir)
                if os.path.isdir(full_path) and re.match(date_pattern, dir):
                    date_dirs.append(dir)
            train_time = max(date_dirs)
        else:
            output_path = f"Utils/output/{task_name}_test_ans"
            dirs = os.listdir(output_path)
            date_pattern = r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$'
            date_dirs = []
            for dir in dirs:
                full_path = os.path.join(output_path, dir)
                if os.path.isdir(full_path) and re.match(date_pattern, dir):
                    date_dirs.append(dir)
            train_time = max(date_dirs)
    
    # load epochs
    if epochs[0] < 0:
        output_path = f"Utils/output/{task_name}_test_ans/{train_time}"
        if os.path.exists(output_path) and generate==False:
            print(f"Output path {output_path} exists. Using existing epochs...")
            dirs = os.listdir(output_path)
            epochs = [int(dir) for dir in dirs if dir.isdigit()]
            epochs.sort()
        else:
            print(f"Output path {output_path} does not exist. Generating outputs...")
            generate = True
            with open(f"Utils/data/{task_name}/config.json", "r") as f:
                config = json.load(f)
                eval_step, eval_step_init, max_epoch = config["eval_step"], config["eval_step_init"], config["max_epoch"]
                epochs = range(eval_step_init, max_epoch + 1, eval_step)

    # generate outputs if need
    original_dir = os.getcwd()
    print("原始目录:", original_dir)
    if generate:
        start_time = datetime.datetime.now()
        for epoch in epochs:
            cmd = f"accelerate launch --config_file ./acc_config.yaml --num_processes={gpus} run.py --task {task_name} --eval --train_time {train_time} --checkpoint_epoch {epoch}"
            print(f"Running command: {cmd}")
            res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(f"Command execution result:\n{res.returncode}")
            end_time = datetime.datetime.now()
            elapsed_time = end_time - start_time
            print(f"Epoch {epoch} - Elapsed time: {elapsed_time}")
            start_time = end_time

    # change to the score output directory
    new_dir = original_dir + f"/Utils/score_output"
    os.chdir(new_dir)
    print("切换到目录:", new_dir)
    success_rate_list, compile_error_rate_list = [], []
    avg_first_success_pos_list, avg_success_rate_list, first_success_count_list = [], [], []

    # run test script for each epoch and collect results
    for epoch in epochs:
        cmd = f"python test-{"sufu" if "sufu" in task_name else "java"}-output.py --task {task_name} --train_time {train_time} --checkpoint_epoch {epoch}"
        print(f"Running command: {cmd}")
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        match1 = re.search(r"Success rate:\s*(\d+\.\d+)%:\s*(\d+)/(\d+)", res.stdout)
        if match1:
            success_rate = match1.group(1)
            success_count = match1.group(2)
            total_count = match1.group(3)
            print(f"Epoch {epoch} - Success rate: {success_rate}% ({success_count}/{total_count})")
            success_rate_list.append(int(success_count)/int(total_count) * 100.0)
        else:
            print(f"Epoch {epoch} - No success rate found in output.")
            success_rate_list.append(0.0)
        match2 = re.search(r"Compilation error rate:\s*(\d+\.\d+)%:\s*(\d+)/(\d+)", res.stdout)
        if match2:
            compile_error_rate = match2.group(1)
            compile_error_count = match2.group(2)
            total_count = match2.group(3)
            print(f"Epoch {epoch} - Compilation error rate: {compile_error_rate}% ({compile_error_count}/{total_count})")
            compile_error_rate_list.append(int(compile_error_count)/int(total_count) * 100.0)
        else:
            print(f"Epoch {epoch} - No compilation error rate found in output.")
            compile_error_rate_list.append(0.0)
        # 新增：捕获平均首次成功位置
        match3 = re.search(r"avg first success position:\s*(\d+\.?\d*)", res.stdout)
        if match3:
            avg_first_success_pos = match3.group(1)
            print(f"Epoch {epoch} - Average first success position: {avg_first_success_pos}")
            avg_first_success_pos_list.append(float(avg_first_success_pos))
        else:
            print(f"Epoch {epoch} - No average first success position found in output.")
            avg_first_success_pos_list.append(0.0)
        # 新增：捕获平均成功率
        match4 = re.search(r"avg success rate:\s*(\d+\.?\d*)%", res.stdout)
        if match4:
            avg_success_rate = match4.group(1)
            print(f"Epoch {epoch} - Average success rate: {avg_success_rate}%")
            avg_success_rate_list.append(float(avg_success_rate))
        else:
            print(f"Epoch {epoch} - No average success rate found in output.")
            avg_success_rate_list.append(0.0)
        # 新增：捕获首次成功计数
        match5 = re.search(r"first success count:\s*(\d+)", res.stdout)
        if match5:
            first_success_count = match5.group(1)
            print(f"Epoch {epoch} - First success count: {first_success_count}")
            first_success_count_list.append(int(first_success_count))
        else:
            print(f"Epoch {epoch} - No first success count found in output.")
            first_success_count_list.append(0)
    
    # print results
    os.chdir(original_dir)
    print("Results for task:", task_name)
    combined_results = list(zip(epochs, success_rate_list, compile_error_rate_list,
                                avg_first_success_pos_list, avg_success_rate_list, first_success_count_list))
    print("Epoch\tSuccess Rate (%) Compile Error Rate (%) Avg First Success Position Avg Success Rate (%) First Success Count")
    for epoch, success_rate, compile_error_rate, avg_first_success_pos, avg_success_rate, first_success_count in combined_results:
        print(f"{epoch}\t{success_rate:.2f}\t\t\t{compile_error_rate:.2f}\t\t\t{avg_first_success_pos:.2f}\t\t\t{avg_success_rate:.2f}\t\t\t{first_success_count}")

if __name__ == "__main__":
    # batch_test_model("sufucoq", gpus=8, epochs=range(100, 901, 100), generate=False)
    # batch_test_model("sufucoqview", gpus=8, epochs=range(10, 201, 10), generate=False)
    # batch_test_model("mbjpcoq", gpus=8, epochs=range(50, 301, 50), generate=False)
    # batch_test_model("mbjpcoqview", gpus=8, epochs=range(20, 101, 20), generate=False)
    # batch_test_model("Qwen2.5-0.5B_sufu", gpus=8, epochs=range(-1, 101, 20), generate=False)
    # batch_test_model("codet5-base_sufu_codeproof", gpus=8, epochs=range(-1, 101, 20), generate=False)
    batch_test_model("codet5-base_mbjp_proofcode", gpus=8, epochs=range(-1, 101, 20), generate=False, train_time="2025-09-24_20-35-59")
    # batch_test_model("codet5p-220m_mbjp", gpus=8, epochs=range(-1, 101, 20), generate=False, train_time="2025-07-03_21-28-26")
    # batch_test_model("codet5p-770m_sufu", gpus=8, epochs=range(-1, 101, 20), generate=False)
    # batch_test_model("codet5p-220m_mbjp", gpus=8, epochs=range(-1, 101, 20), generate=False)
    # batch_test_model("codet5-base_mbjp", gpus=8, epochs=range(-1, 101, 20), generate=False)
