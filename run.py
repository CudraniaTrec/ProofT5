import torch, swanlab
from torch import optim
from accelerate import Accelerator
from accelerate.utils import InitProcessGroupKwargs
from tqdm import tqdm, trange
import numpy as np
import os, sys, json, random, time, pickle, shutil
sys.setrecursionlimit(500000000)
import argparse, traceback, beeprint
from datetime import timedelta, datetime
from Utils.evaluator.CodeBLEU import calc_code_bleu

from Dataset import SumDataset, ChunkedRandomSampler, rs_collate_fn, rs_collate_fn_cutprefix
from Model import MyT5, MyT5withCoq1, MyT5withCoq2
from beamsearch import BeamSearch
from beamsearch_coq import BeamSearch as BeamSearchCoq
from beamsearch_dsl import BeamSearch as BeamSearchDsl
from beamsearch_sufu import BeamSearch as BeamSearchSufu

class Dotdict(dict):
    def __getattr__(self, name):
        return self[name]
    def __setattr__(self, name, value):
        self[name] = value
    def __delattr__(self, name):
        del self[name]
args = Dotdict({
    "NlLen": 512,           # Maximum length of natural language input
    "CodeLen": 512,         # Maximum length of code output
    "batch_size": 10,       # Batch size
    "batch_size_eval": 5,   # Batch size for beam search evaluation
    "embedding_size": 768,  # Dimension of embeddings
    "rulenum": 32216,       # Number of rules(types of tokens)
    "max_coqview_len": 160, # Maximum length of coqview
    "seed": 19970316,       # Random seed
    "lr":1e-4,              # Learning rate
    "max_epoch": 1000,      # Maximum number of epochs
    "mask_id": 0,           # Mask/Pad token id
    "eval_step": 20,        # Evaluate model every eval_step
    "eval_step_init": 40,  # Evaluate model after eval_step_init
    "patience": 5,          # max number of epochs w/o improvement, reload model
    "max_num_trials": 3,    # max number of reloading before early stop
    "metric":"bleu",        # Model evaluation metric
    "precision": "bf16",    # Precision
    "task": "mbjp",         # Task name
    "eval": False,           # Evaluate model
    "train_time": "",
    "checkpoint_epoch": 200,
    "cut_prefix": False,     # Cut prefix from code output
    "empty_cuda_cache": 100, # Empty CUDA cache every empty_cuda_cache epochs
    "enable_coqview": False, # Enable coqview model
    "validation": True,      # Enable validation during training
    "pretrain_name": "pretrain", # Pretrained model name
})

class Communicate:
    def __init__(self, file_name="tmp/communicate.json"):
        self.filename = file_name
    def set(self, name, value):
        with open(self.filename, "r") as f:
            info = json.load(f)
        info[name] = value
        with open(self.filename, "w") as f:
            json.dump(info, f)
    def get(self, name):
        with open(self.filename, "r") as f:
            info = json.load(f)
        return info[name]
commu = Communicate()

def save_model(model, dirs="Utils/models/Default/", model_type="best"):
    if not os.path.exists(dirs):
        os.makedirs(dirs)
    torch.save(model.state_dict(), f"{dirs}{model_type}_model.ckpt")

def load_model(model, dirs="Utils/models/Default/", model_type="best"):
    path = os.path.join(dirs, f"{model_type}_model.ckpt")
    if os.path.exists(path):
        model.load_state_dict(torch.load(path, map_location="cpu"), strict=False)
    else:
        path = os.path.join(dirs, f"last_model.ckpt") # load last model
        if os.path.exists(path):
            model.load_state_dict(torch.load(path, map_location="cpu"), strict=False)
        else:
            print(f"Model not found in {dirs}")
            exit(1)

def split_data(process_num, tasktype):
    data = pickle.load(open(f"Utils/data/{args.task}/{tasktype}.pkl", "rb"))
    if len(data) % process_num != 0:
        datalen = len(data) // process_num + 1
    else:
        datalen = len(data) // process_num
    avg_len_list = [datalen] * process_num
    for i in range(datalen * process_num - len(data)):
        avg_len_list[i] -= 1
    split_point = 0
    for i in range(process_num):
        pickle.dump(
            data[split_point : split_point + avg_len_list[i]], open(f"tmp/data_{tasktype}{i}.pkl", "wb")
        )
        split_point += avg_len_list[i]
    commu.set(f"{tasktype}_data_len", avg_len_list)
    print(f"{tasktype}_set length : {commu.get(f"{tasktype}_data_len")}, total length : {len(data)}")

def finetune():
    global args
    date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    taskconfig = json.loads(open("Utils/data/%s/config.json" % args.task, "r").read())
    for key in taskconfig:
        setattr(args, key, taskconfig[key])
        if key == "max_code_len":
            args.CodeLen = taskconfig[key]

    # Initialize accelerator & split train, dev, test data
    accelerator = Accelerator(mixed_precision=args.precision,
                              kwargs_handlers=[InitProcessGroupKwargs(timeout=timedelta(seconds=3600))])
    if accelerator.is_main_process:
        split_data(accelerator.num_processes, "train")
        if "pretrain" not in args.task:
            if args.validation:
                split_data(accelerator.num_processes, "valid")
            split_data(accelerator.num_processes, "test")
    accelerator.wait_for_everyone()

    # configuration
    pindex = accelerator.process_index
    torch.manual_seed(args.seed + accelerator.process_index)
    np.random.seed(args.seed + accelerator.process_index)
    random.seed(args.seed + accelerator.process_index)
    device = accelerator.device

    # load word table & model
    newruledic = pickle.load(open(f"Utils/data/{args.task}/rules.pkl", "rb"))
    if args.enable_coqview:
        model = MyT5withCoq1(args)
    else:
        model = MyT5(args)
    load_model(model, "Utils/models/Model%s/" % args.pretrain_name)
    args.rulenum = len(newruledic)
    model.resize_token_embeddings(args.rulenum)
    
    # load dataset & print configuration
    train_set = SumDataset(args, "train", idx=accelerator.process_index)
    if "pretrain" not in args.task:
        dev_set = SumDataset(args, "valid" if args.validation else "test", idx=accelerator.process_index)
        test_set = SumDataset(args, "test", idx=accelerator.process_index)
    if accelerator.is_main_process:
        print("Model loaded")
        print("config is :", end = " ")
        beeprint.pp(args)

    #prepare optimizer
    accelerator.state.deepspeed_plugin.deepspeed_config[
        "train_micro_batch_size_per_gpu"
    ] = args.batch_size
    optimizer = optim.AdamW(model.parameters(), eps=1e-8, lr=args.lr)
    model, optimizer = accelerator.prepare(model, optimizer)
    accelerator.register_for_checkpointing(model)
    accelerator.register_for_checkpointing(optimizer)

    # Evaluate model
    if args.eval:
        if args.train_time:
            load_model(model.module, f"Utils/models/Model{args.task}/{args.train_time}/", model_type=f"epoch{args.checkpoint_epoch}")
        else:
            load_model(model.module, f"Utils/models/Model{args.task}/")
        testmodel(test_set, model, device, accelerator, newruledic)
        exit(0)

    # Fine-tune model
    swanlab.init(
        project=args.task,
        experiment_name=f"{args.task}_{date}",
        config={
            "learning_rate": args.lr, 
        },
    )
    num_trial = patience = 0
    maxBleu = 0
    for epoch in trange(args.max_epoch+1, desc=f"Processer {pindex}"):
        # eval model using dev set, early stop if no improvement
        if epoch % args.eval_step == 0 and epoch >= args.eval_step_init:
            if args.validation:
                tnum, bleu = evalmodel(dev_set, model, device, accelerator, newruledic)
                if accelerator.is_main_process:
                    unwrapped_model = accelerator.unwrap_model(model)
                    save_model(unwrapped_model, f"Utils/models/Model{args.task}/", model_type="last")
                    save_model(unwrapped_model, f"Utils/models/Model{args.task}/{date}/", model_type=f"epoch{epoch}")
                    commu.set("reload", False)
                    commu.set("exit", False)
                    
                    if maxBleu < bleu:
                        maxBleu = bleu
                        patience = 0
                        save_model(unwrapped_model, f"Utils/models/Model{args.task}/", model_type="best")
                        save_model(unwrapped_model, f"Utils/models/Model{args.task}/{date}/", model_type="best")
                    else:
                        patience += 1
                        if patience >= args.patience:  # patience exhausted, reload
                            num_trial += 1
                            if num_trial >= args.max_num_trials:
                                print("Early stop!")
                                commu.set("exit", True)
                            commu.set("reload", True)
                            print("Reload model")
                            patience = 0
                    print(f"dev_bleu: {bleu}, patience: {patience}, trial: {num_trial}")
                    swanlab.log({
                            "dev_bleu": bleu,
                            "patience": patience,
                            "trial": num_trial,
                    })
                accelerator.wait_for_everyone()
                if commu.get("exit"):
                    exit(0)
                if commu.get("reload"):
                    load_model(model.module, f"Utils/models/Model{args.task}/")
                    for param_group in optimizer.param_groups:
                        param_group["lr"] = 0.5 * param_group["lr"]
                accelerator.wait_for_everyone()
            else:
                if accelerator.is_main_process:
                    unwrapped_model = accelerator.unwrap_model(model)
                    save_model(unwrapped_model, f"Utils/models/Model{args.task}/", model_type="last")
                    save_model(unwrapped_model, f"Utils/models/Model{args.task}/{date}/", model_type=f"epoch{epoch}")
        
        tot_runtime = 0
        sampler = ChunkedRandomSampler(train_set, args.batch_size)
        data_loader = torch.utils.data.DataLoader(
            dataset=train_set,
            batch_size=args.batch_size,
            drop_last=False,
            num_workers=10,
            collate_fn=rs_collate_fn_cutprefix if args.cut_prefix else rs_collate_fn,
            sampler=sampler,
            pin_memory=True,
        )

        batch_num=0
        model.train()
        for dBatch in data_loader:
            for x in dBatch:
                dBatch[x] = dBatch[x].to(device)
            starttime = time.time()
            if args.enable_coqview:
                loss, info = model(dBatch["nl"], dBatch["res"], dBatch["coqview"], 
                                   inputprefix=dBatch["prefix"] if args.cut_prefix else None)
            else:
                loss, info = model(dBatch["nl"], dBatch["res"])
            tot_runtime += time.time() - starttime

            if loss.item() == np.inf:
                with open("tmp/log.txt", "w") as f:
                    f.write(f"inf loss at process {pindex}, epoch {epoch}, batch {batch_num}\n")
                    f.write(f"nl: {dBatch['nl']}\n")
                with open("tmp/dbatch.pkl", "wb") as f:
                    pickle.dump(dBatch, f)
                save_model(model.module, f"Utils/models/Model{args.task}/", model_type="last")
                assert 0
            batch_num += 1
            accelerator.backward(loss)
            optimizer.step()  
            optimizer.zero_grad()
            lr = optimizer.param_groups[0]["lr"]
            swanlab.log({"loss": loss.item(), "lr": lr})
            if epoch % args.eval_step == 0 and epoch >= args.eval_step_init:
                swanlab.log({"loss_eval": loss.item()})
            if "sigma1" in info:
                swanlab.log({"sigma1": info["sigma1"].item(), "sigma2": info["sigma2"].item()})
                swanlab.log({"loss1": info["loss1"].item(), "loss2": info["loss2"].item()})
        swanlab.log({"runtime": tot_runtime / batch_num})
        if epoch % args.empty_cuda_cache == 0:
            torch.cuda.empty_cache()

@torch.no_grad()
def evalmodel(dev_set, model, device, accelerator, newruledic):
    batch_size = args.batch_size
    data_offset = sum(commu.get("valid_data_len")[:accelerator.process_index])
    data_loader = torch.utils.data.DataLoader(
        dataset=dev_set,
        batch_size=batch_size,
        drop_last=False,
        num_workers=2,
        collate_fn=rs_collate_fn,
        shuffle=False,
        pin_memory=True,
    )
    beamsize = 3
    if "coq" in args.task or "grammar" in args.task:
        beam = BeamSearchCoq(beamsize, newruledic, checkcoq=False)
    elif "nocheck" in args.task:
        beam = BeamSearchCoq(beamsize, newruledic, checkcoq=False, check_grammar=False)
    elif "dsl" in args.task:
        beam = BeamSearchDsl(beamsize, newruledic)
    else:
        beam = BeamSearch(beamsize, newruledic)

    model.eval()
    f = open("tmp/out_val%d.txt" % int(accelerator.process_index), "w")
    for index,dBatch in enumerate(data_loader):
        batch_len = len(dBatch["nl"])
        offset = data_offset + index * batch_size
        dBatch["nl"] = dBatch["nl"].to(device).repeat_interleave(beamsize, dim=0)
        ans = beam.search(
            dBatch["nl"], model, max_len=args.CodeLen,
            desc=f"Problem {offset}-{offset+batch_len-1}", offset=offset
        )
        for i in range(len(ans)):
            try:
                code = ans[i].final_set[0]
                # remove annotations and \n
                code = " ".join([line for line in code.split("\n") if not line.strip().startswith("//")])
            except IndexError as e:
                code = f"IndexError: {e}"
            f.write(code + "\n")
    f.close()

    accelerator.wait_for_everyone()
    if accelerator.is_main_process:
        os.system(": > tmp/out.txt")
        for i in range(accelerator.num_processes):
            os.system("cat tmp/out_val%d.txt >> tmp/out.txt" % i)
        tnum, codebelu = calc_code_bleu.get_codebleu(
            f"Utils/data/{args.task}/groundvalid.txt",
            "tmp/out.txt",
            "java",
            benchmark=args.task,
        )
        return tnum, codebelu
    else:
        return 0, 0

@torch.no_grad()
def testmodel(data_set, model, device, accelerator, newruledic):
    batch_size = args.batch_size_eval 
    tasktype = data_set.dataName # valid or test
    data_offset = sum(commu.get(f"{tasktype}_data_len")[:accelerator.process_index])
    print(f"Task type: {tasktype}")
    data_loader = torch.utils.data.DataLoader(
        dataset=data_set,
        batch_size=batch_size,
        drop_last=False,
        num_workers=2,
        collate_fn=rs_collate_fn,
        shuffle=False,
        pin_memory=True,
    )
    
    beamsize = 10
    if "sufu" in args.task:
        beam = BeamSearchSufu(beamsize, newruledic, type_ctx_len=args.max_coqview_len,
                              type_check=(args.task=="sufucoq"), 
                              add_type_ctx=(args.task=="sufucoqview"),
                              check_grammar=(args.task!="sufunocheck"))
    # mbjp humaneval
    elif args.enable_coqview:
        beam = BeamSearchCoq(beamsize, newruledic, coqview_len=args.max_coqview_len, addCoqview=True)
    elif "coq" in args.task:
        beam = BeamSearchCoq(beamsize, newruledic, checkcoq=True)
    elif "grammar" in args.task:
        beam = BeamSearchCoq(beamsize, newruledic, checkcoq=False)
    elif "nocheck" in args.task:
        beam = BeamSearchCoq(beamsize, newruledic, checkcoq=False, check_grammar=False)
    elif "dsl" in args.task:
        beam = BeamSearchDsl(beamsize, newruledic)
    else:
        beam = BeamSearch(beamsize, newruledic)
    
    target_folder = f"Utils/output/{args.task}_{tasktype}_ans/"
    if args.train_time:
        target_folder += f"{args.train_time}/{args.checkpoint_epoch}/"
    if accelerator.is_main_process:
        if os.path.exists(target_folder):
            shutil.rmtree(target_folder)
        os.makedirs(target_folder)

    accelerator.wait_for_everyone()
    model.eval()
    for index, dBatch in enumerate(data_loader):
        offset = data_offset + index * batch_size
        batch_len = len(dBatch["nl"])
        ans = beam.search(
            dBatch["nl"].to(device).repeat_interleave(beamsize, dim=0),
            model, 
            max_len=args.CodeLen,
            desc = f"Problem {offset}-{offset+batch_len-1}", 
            offset=offset,
            init_tokens=dBatch["prefix"].to(device) if "prefix" in dBatch else None,)
        for i in range(len(ans)):
            for k in range(beamsize):
                file_path = f"{target_folder}{offset+i}_{k}.txt"
                with open(file_path, "w") as f:
                    try:
                        code = ans[i].final_set[k]
                    except IndexError as e:
                        code = f"IndexError: {e}"
                    f.write(code)
        print(f"{offset} to {offset + batch_len - 1} saved to {target_folder}")
                  
if __name__ == "__main__":
    np.set_printoptions(threshold=sys.maxsize)
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, required=True)
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--train_time", type=str, default="")
    parser.add_argument("--checkpoint_epoch", type=int, default=200)
    argc = parser.parse_args()
    # mbjp, mbjp_blind, mbjpcoq, mbjpcoqview, mbjp_dsl, mbjpcoq_770m, mbjpcoqview_770m
    # humaneval_blind, humanevalcoq, humanevalcoqview
    # sufugrammar, sufucoq, sufucoqview
    # pretrain, pretrain_770m
    args.task = argc.task 
    if argc.eval:
        args.eval = True
        args.train_time = argc.train_time
        args.checkpoint_epoch = argc.checkpoint_epoch
    finetune()