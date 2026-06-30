def export_vocabulary(tokenizer, output_file="vocabulary.txt"):
    """导出tokenizer的完整词表"""
    
    # 方法1：如果tokenizer有vocab属性
    if hasattr(tokenizer, 'vocab'):
        vocab = tokenizer.vocab
        # 按token ID排序
        sorted_vocab = sorted(vocab.items(), key=lambda x: x[1])
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for token, token_id in sorted_vocab:
                f.write(f"{token_id}\t{token}\n")
        
        print(f"词表已导出到 {output_file}")
        return vocab
    
    # 方法2：通过get_vocab()方法
    elif hasattr(tokenizer, 'get_vocab'):
        vocab = tokenizer.get_vocab()
        sorted_vocab = sorted(vocab.items(), key=lambda x: x[1])
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for token, token_id in sorted_vocab:
                f.write(f"{token_id}\t{token}\n")
        
        return vocab
    
    # 方法3：遍历所有可能的token ID
    else:
        vocab_size = tokenizer.vocab_size
        vocab = {}
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for i in range(vocab_size):
                try:
                    token = tokenizer.decode([i])
                    vocab[token] = i
                    f.write(f"{i}\t{token}\n")
                except:
                    f.write(f"{i}\t[UNKNOWN]\n")
        
        return vocab

# 导出词表
import pickle, json
with open(f"data/tokenizer.pkl", "rb") as f:
    tokenizer = pickle.load(f)
vocab = export_vocabulary(tokenizer)
with open("data/vocabulary.txt", "w", encoding="utf-8") as f:
    for token, token_id in sorted(vocab.items(), key=lambda x: x[1]):
        f.write(f"{token_id}\t{token}\n")
print(f"词表大小: {len(vocab)}")