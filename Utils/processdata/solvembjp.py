import pickle,json, os
from .solvedata import parserTree
from .stringfy import strfy
from .solvetree import processaction
from .process_utils import postfix
path = os.path.split(os.path.realpath(__file__))[0]
#convert dataset in json format into [Tree]
def process_data(dataset_name, dataset_type):
    # ./data/mbjp/
    dump_path = f'{path}/../data/{dataset_name}/'
    dataset_load_path = f'{dump_path}/{dataset_name}_{dataset_type}.pkl'
    dataset = pickle.load(open(dataset_load_path, 'rb'))

    datas = []
    for entry in dataset:
        if entry['java_code'] == None:
            continue
        elif entry['description'] == None:
            continue
        datas.append({'nl':entry['description'], 'function':entry["java_code"]})
    # dump natural language data for generation phase
    if dataset_type in ['valid', 'test']:
        nl_data = [entry['nl'] for entry in datas]
        json.dump(nl_data, open(f'{dump_path}/{dataset_type}_nl.json', 'w'))
        #data/mbjp/valid/0.pkl
        dump_nl_path = f'{dump_path}/{dataset_type}/'
        for i, entry in enumerate(nl_data):
            pickle.dump(entry, open(dump_nl_path + str(i) + ".pkl", "wb"))
    
    json.dump(datas, open(f'{dump_path}/{dataset_type}.json', 'w'))
    print(f'Processing {dataset_name} {dataset_type} dataset, total {len(datas)} entries')

    pdata, _ = parserTree(datas)
    # dump standard code for validation during finetuning
    if dataset_type == 'valid':
        # data/mbjp/groundvalid.txt
        with open(f'{dump_path}/groundvalid.txt', 'w') as f:
            for i in range(len(pdata)):
                tmpstr = strfy(pdata[i]['root'], lang='java')
                tmpstr = tmpstr.replace('\n', ' ').replace('\t', ' ')
                f.write(tmpstr  + '\n')
    return pdata

if __name__ == "__main__":
    dataset_name = "mbjp" if postfix == "_java" else "mbjp_blind"
    train_data = process_data(dataset_name, 'train')
    valid_data = process_data(dataset_name, 'valid')
    test_data  = process_data(dataset_name, 'test')

    print("="*25 + "Post Processing(Sequentialization)" + "="*25)
    ptraindata, rules = processaction(train_data)
    pvaliddata, rules = processaction(valid_data, rules)
    ptestdata , rules = processaction(test_data, rules)
    
    path = f'{path}/../data/{dataset_name}/'
    pickle.dump(ptraindata, open(f'{path}/train.pkl', 'wb'))
    pickle.dump(pvaliddata, open(f'{path}/valid.pkl', 'wb'))
    pickle.dump(ptestdata, open(f'{path}/test.pkl', 'wb'))
    pickle.dump(rules, open(f'{path}/rules.pkl', 'wb'))

    print(f"Train len: {len(ptraindata)} Valid len: {len(pvaliddata)} Test len: {len(ptestdata)} ")
    print(f"Rules size: {len(rules)}")