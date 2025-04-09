TOKENIZERS_PARALLELISM=true
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7
TORCH_DISTRIBUTED_DEBUG=OFF

accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjpcoq --eval --train_time 2025-03-03_14-35-32 --checkpoint_epoch 200
accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjpcoq --eval --train_time 2025-03-03_14-35-32 --checkpoint_epoch 300
accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjpcoq --eval --train_time 2025-03-03_14-35-32 --checkpoint_epoch 400
accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjpcoq --eval --train_time 2025-03-03_14-35-32 --checkpoint_epoch 500
# accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjp_dsl --eval