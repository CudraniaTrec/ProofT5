import pickle
import tempfile
import unittest
from pathlib import Path

from Dataset import SumDataset


class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class EvaluationOnlyDatasetTest(unittest.TestCase):
    def test_sum_dataset_accepts_empty_evaluation_only_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shard = tmp_path / "data_train0.pkl"
            with shard.open("wb") as f:
                pickle.dump([], f)

            config = AttrDict({
                "runtime_dir": str(tmp_path),
                "mask_id": 0,
                "model_family": "t5gemma2",
            })
            dataset = SumDataset(config, "train", idx=0)

            self.assertEqual(len(dataset), 0)


if __name__ == "__main__":
    unittest.main()
