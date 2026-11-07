"""Recreate the optional pre-expanded default timeline. The engine derives it internally."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'starter'))
import check_submission as cs
out=root/'data/timeline_default.csv'
cs.prepare_inputs(cs.default_portfolio())['frame'].to_csv(out,index=False)
print(out)
