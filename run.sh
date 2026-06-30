accelerate launch --config_file ./acc_config.yaml  --num_processes=8 run.py --task pretrain_770m
# accelerate launch --config_file ./acc_config.yaml  --num_processes=8 run.py --task sufugrammar --eval
# python batch_test_model.py
# accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task sufucoqview --eval --train_time 2025-06-10_19-03-59 --checkpoint_epoch 100
# accelerate launch --config_file ./acc_config.yaml --num_processes=7 run.py --task mbjpcoqview 
# accelerate launch --config_file ./acc_config.yaml --num_processes=1 run.py --task sufugrammar --eval --train_time 2025-05-11_16-14-51 --checkpoint_epoch 500
# accelerate launch --config_file ./acc_config.yaml --num_processes=8 run.py --task mbjp_dsl --eval