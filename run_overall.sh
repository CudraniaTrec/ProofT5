#!/bin/bash

# 保存原始的标准输出和标准错误
exec 3>&1 4>&2
# 将所有输出重定向到 log.txt
# exec > tmp/log.txt 2>&1

# 0. set environment variables
TOKENIZERS_PARALLELISM=true
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7
TORCH_DISTRIBUTED_DEBUG=OFF
# conda activate py313

# 1. prepare data
echo "==================== Prepare data ===================="
cd coq_model
# generate train/valid/test data
python prepare_data.py
cd ..

# 2. train/eval model on mbjp
echo "==================== Train/eval model on mbjp ===================="
cd Utils
TARGET_FILE=processdata/process_utils.py
update_and_run() {
    NEW_FIRST_LINE="$1"
    sed -i "1c$NEW_FIRST_LINE" "$TARGET_FILE"
    echo "The first line of '$TARGET_FILE' has been updated to: $NEW_FIRST_LINE"
    python -m processdata.solvembjp
}
# 更新文件第一行为 '_java' 并运行模块
update_and_run "postfix = '_java'"
cd ..
accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjp
accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjp --eval
cd Utils/score_output
python test-mbjp-output.py --task mbjp
cd ../..

# 3. train/eval model on mbjp_blind
echo "==================== Train/eval model on mbjp_blind ===================="
# 更新文件第一行为 '_blind' 并再次运行模块
cd Utils
update_and_run "postfix = '_blind'"
cd ..  
accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjp_blind
accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjp_blind --eval
cd Utils/score_output
python test-mbjp-output.py --task mbjp_blind
cd ../..

# 4. train/eval model on mbjpcoq
echo "==================== Train/eval model on mbjpcoq ===================="
accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjpcoq
accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjpcoq --eval
cd Utils/score_output
python test-mbjp-output.py --task mbjpcoq
cd ../..

# 恢复原始的标准输出和标准错误
# exec 1>&3 2>&4
# 关闭保存的文件描述符
exec 3>&- 4>&-