import numpy as np
import random

def msp(sequence):
    def extract_and_replace(masks, seq):
        extracted = []  # 存储提取的内容
        processed_seq = []  # 存储处理后的数组
        i = 0  # 用于标记<extra_id_{i}>
        in_sequence = False
        
        for idx, val in enumerate(masks):
            if val == 1:
                if not in_sequence:
                    # 开始新的连续 1 序列
                    processed_seq.append(f"<extra_id_{i}>")
                    extracted.append(f"<extra_id_{i}>")
                    in_sequence = True
                extracted.append(seq[idx])
            else:
                if in_sequence:
                    # 结束当前的 1 序列
                    i += 1
                in_sequence = False
                processed_seq.append(seq[idx])
        return processed_seq, extracted
    
    def generate_msp_mask(sequence_length, mask_ratio=0.15, lambda_poisson=3):
        """
        Generate a mask sequence for MSP (Masked Span Prediction) task.

        Args:
            sequence_length (int): The length of the input sequence.
            mask_ratio (float): The proportion of tokens to be masked.
            lambda_poisson (int): The lambda parameter for Poisson distribution determining span length.

        Returns:
            np.array: A binary mask of length `sequence_length`, where 1 indicates a masked token.
        """
        mask = np.zeros(sequence_length, dtype=int)  # Initialize all tokens as unmasked (0)
        num_to_mask = int(sequence_length * mask_ratio)  # Total tokens to mask

        masked_count = 0
        while masked_count < num_to_mask:
            span_length = np.random.poisson(lambda_poisson) + 1  # Poisson sampled span length (at least 1)
            start_idx = np.random.randint(0, sequence_length)  # Random start position

            # Ensure the selected span does not exceed the sequence bounds
            end_idx = min(start_idx + span_length, sequence_length)
            
            # Apply mask (only if the region is not already masked)
            for i in range(start_idx, end_idx):
                if mask[i] == 0 and masked_count < num_to_mask:
                    mask[i] = 1
                    masked_count += 1

        return mask

    masks = generate_msp_mask(len(sequence))
    return extract_and_replace(masks,sequence)

def continue_split(sequence):
    split_idx = random.randint(len(sequence) // 10,  9 * (len(sequence) // 10))
    part1 = sequence[:split_idx]  # 前部分
    part2 = sequence[split_idx:]  # 后部分

    return part1, part2