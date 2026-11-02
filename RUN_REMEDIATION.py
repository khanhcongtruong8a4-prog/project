from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent/'panda_research/scripts'))
from bootstrap_guarded_qp_reliability import main
raise SystemExit(main())
