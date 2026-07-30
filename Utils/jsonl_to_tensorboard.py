import argparse
import json
import os

from torch.utils.tensorboard import SummaryWriter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    writer = SummaryWriter(args.output_dir)
    steps = {}
    count = 0
    with open(args.input) as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            for key, value in record.items():
                if key == "time" or not isinstance(value, (int, float)):
                    continue
                step = steps.get(key, 0)
                writer.add_scalar(key, value, step)
                steps[key] = step + 1
                count += 1
    writer.flush()
    writer.close()
    print(f"wrote {count} scalars to {args.output_dir}")


if __name__ == "__main__":
    main()
