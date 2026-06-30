import json, pickle
from transformers import AutoTokenizer
# Load the tokenizer
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-small", local_files_only=True)
with open("coq_model/new_tokens.json", 'r') as f:
    new_tokens = json.load(f)
tokenizer.add_tokens(new_tokens)
with open("SuFu/new_tokens.json", 'r') as f:
    new_tokens = json.load(f)
tokenizer.add_tokens(new_tokens)
rules = tokenizer.get_vocab()
print(f"Number of tokens in the tokenizer: {len(rules)}")
# Save the tokenizer with the new tokens
with open("Utils/data/rules.json", 'w') as f:
    json.dump(rules, f, indent=4)
with open("Utils/data/rules.pkl", 'wb') as f:
    pickle.dump(rules, f)
with open("Utils/data/tokenizer.pkl", 'wb') as f:
    pickle.dump(tokenizer, f)