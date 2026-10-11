from pathlib import Path

from pharmproject.config import Config
from pharmproject.pipeline.base import PipelineContext
from pharmproject.stages.stage2_descriptors import Stage2Descriptors
from pharmproject.storage.store import ZINC22_SCHEMA, ParquetShardWriter

base = Path(".smoke_stage2_logs")
in_dir = base / "raw" / "pubchem" / "shards"
w = ParquetShardWriter(in_dir, 100000, schema=ZINC22_SCHEMA)
for i in range(300000):
    w.add({"zinc_id": str(i), "smiles": "CCO", "tranche": "t"})
w.close()

cfg = Config(
    data_dir=str(base),
    stage2={"input_dir": "raw/pubchem/shards", "output_dir": "intermediate/stage2_filtered", "shard_rows": 50000},
)
out = Stage2Descriptors().run(PipelineContext(config=cfg))
print("FINAL stats:", out.stats)
