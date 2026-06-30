from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(
    "Salesforce/codet5-small", min_length=4, local_files_only=True)
print(tokenizer.tokenize("public static int main(String[] args) { return 0; }"))
print(tokenizer.encode("public static int main(String[] args) { return 0; }"))