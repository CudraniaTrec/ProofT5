import os
from transformers import T5ForConditionalGeneration, T5Config, T5Tokenizer
import torch
from pathlib import Path

def download_codet5_large():
    # 设置模型名称和保存路径
    model_name = "Salesforce/codet5-large"
    save_dir = "./Utils/models/Modelcodet5-large/"
    
    # 创建保存目录
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    print(f"开始下载CodeT5-large模型...")
    print(f"保存路径: {save_dir}")
    
    # 方法1: 使用transformers库下载并保存为.ckpt格式
    print("正在下载模型权重...")
    model = T5ForConditionalGeneration.from_pretrained(model_name)
    print("正在下载配置文件...")
    config = T5Config.from_pretrained(model_name)
    
    # 保存配置文件为config.json
    config_path = os.path.join(save_dir, "config.json")
    config.save_pretrained(save_dir)
    print(f"配置文件已保存到: {config_path}")
    
    # 保存模型权重为.ckpt格式
    ckpt_path = os.path.join(save_dir, "best_model.ckpt")
    torch.save({
        'model_state_dict': model.state_dict(),
        'config': config.to_dict(),
        'model_type': 'codet5-large'
    }, ckpt_path)
    print(f"模型权重已保存到: {ckpt_path}")
    
    print("下载完成！")
    
    # 显示文件信息
    print("\n下载的文件:")
    for file in os.listdir(save_dir):
        file_path = os.path.join(save_dir, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            print(f"  {file}: {size:.2f} MB")
    return True

if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"使用设备: {device}")
    download_codet5_large()