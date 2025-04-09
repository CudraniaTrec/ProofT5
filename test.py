# import pickle, torch, json
# from Dataset import SumDataset, rs_collate_fn
# from beamsearch_coq import BeamSearch, tokenizer, vocabsize, rule_dict, verbose
# from run import args, load_model, split_data
# from Model import MyT5withCoq

# print(f"rule_size: {len(rule_dict)}")
# rrule_dict = {v:k for k,v in rule_dict.items()}

# args.task = "mbjpcoqview"
# data_set = SumDataset(args, "test", idx=0)

# model = MyT5withCoq(args)
# args.rulenum = vocabsize
# model.resize_token_embeddings(vocabsize)
# load_model(model, f"Utils/models/Modelmbjpcoqview/", model_type="last")
# model.to("cuda")
# model.eval()

# data_loader = torch.utils.data.DataLoader(
#         dataset=data_set,
#         batch_size=5,
#         drop_last=False,
#         num_workers=2,
#         collate_fn=rs_collate_fn,
#         shuffle=True,
#         pin_memory=True,
# )

# beamsize = 3
# beam = BeamSearch(beamsize, rule_dict, checkcoq=True)
# device = "cuda"
# f = open("tmp/out.txt", "w")
# for index, dBatch in enumerate(data_loader):
#     # rule_list = dBatch["res"][0].tolist()
#     # print("="*50)
#     # print(rule_list)
#     # print([rrule_dict[r] for r in rule_list])
#     batch_len = len(dBatch["nl"])
#     dBatch["nl"] = dBatch["nl"].to(device).repeat_interleave(beamsize, dim=0)
#     ans = beam.search(
#         dBatch["nl"], model, max_len=args.CodeLen)
#     for i in range(len(ans)):
#         try:
#             code = ans[i].final_set[0]
#         except IndexError as e:
#             code = f"IndexError: {e}"
#         f.write(code + "\n")
# f.close()

from beamsearch_naive import BeamSearch, SearchNode, identifiers, strfy
import pickle, torch, json
from run import args, load_model, split_data
from Dataset import SumDataset, rs_collate_fn

with open("Utils/data/mbjp_dsl/train.pkl", "rb") as f:
    train_data = pickle.load(f)
with open("Utils/data/mbjp_dsl/valid.pkl", "rb") as f:
    valid_data = pickle.load(f)
with open("Utils/data/mbjp_dsl/test.pkl", "rb") as f:
    test_data = pickle.load(f)
with open("Utils/data/mbjp_dsl/rules.pkl", "rb") as f:
    ruledict = pickle.load(f)

expandedname = []  # node name to be expanded
for rule in ruledict:
    tmpname = rule.strip().split()[0]
    # x could be a rule or a terminal
    # rule: "start -> java"
    # terminal: "maxcount"
    if len(rule.strip().split()) < 3:
        continue
    expandedname.append(tmpname)
expandedname.extend(identifiers)

for entry in train_data:
    rulelist = entry["rulelist"][1:-1]
    node = SearchNode(ruledict, expandedname)
    for rule in rulelist:
        node.apply(rule, 0.1)
    print(strfy(node.root.getTreestr()))
    break