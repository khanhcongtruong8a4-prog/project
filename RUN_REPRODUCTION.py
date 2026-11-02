"""Restore the complete evidence, then verify or rerun the frozen A2 suites."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'panda_research/scripts'))
import argparse,subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',help='Execute fresh original-seven plus v4-twelve motion cells')
    parser.add_argument('--verify-only',action='store_true',help='Restore inputs and verify without new motion (default)')
    parser.add_argument('--prefix');parser.add_argument('--scratch',type=Path)
    args=parser.parse_args()
    if args.run and args.verify_only:parser.error('Choose --run or --verify-only')
    if (ROOT/'evidence').is_dir():
        from archive_regular_evidence import restore as restore_regular
        from archive_evidence import restore as restore_ctz
        regular=restore_regular(ROOT/'evidence',ROOT,args.scratch)
        traces=restore_ctz(ROOT/'evidence',ROOT,args.scratch)
        print('Restored exact files',len(regular['files']),'CTZ',len(traces['files']),flush=True)
    command=[sys.executable,str(ROOT/'panda_research/scripts/reproduce_a2_acceptance.py')]
    if not args.run:command.append('--verify-only')
    if args.prefix:command+=['--prefix',args.prefix]
    return subprocess.call(command,cwd=ROOT/'panda_research')


if __name__=='__main__':raise SystemExit(main())
