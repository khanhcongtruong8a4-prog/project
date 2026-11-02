"""Packaged as APPLY_OVERLAY.py next to PACKAGE_MANIFEST.json; no dependencies."""
from pathlib import Path,PurePosixPath
import argparse
import hashlib
import json
import shutil


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def safe(root,name):
    relative=PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe archive path')
    result=(root/str(relative)).resolve()
    if not result.is_relative_to(root.resolve()):raise ValueError('Path escapes selected root')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True,help='Unpacked accepted r2 panda_research directory')
    args=parser.parse_args()
    package=Path(__file__).resolve().parent;base=args.baseline.resolve()
    manifest=json.loads((package/'PACKAGE_MANIFEST.json').read_text())
    for name,expected in manifest['package_files'].items():
        p=safe(package,name)
        if not p.is_file() or sha(p)!=expected:raise ValueError('Package hash mismatch: '+name)
    for name,expected in manifest['immutable_base_files'].items():
        p=safe(base,name)
        if not p.is_file() or sha(p)!=expected:raise ValueError('Wrong or modified accepted baseline: '+name)
    pending=[]
    for row in manifest['install_files']:
        source=safe(package,row['package_path']);target=safe(base,row['target'])
        if target.exists():
            current=sha(target)
            if current==row['new_sha256']:continue
            if row['baseline_sha256'] is None or current!=row['baseline_sha256']:
                raise ValueError('Local file differs; nothing was written: '+row['target'])
        elif row['baseline_sha256'] is not None:
            raise ValueError('Missing accepted file; nothing was written: '+row['target'])
        if target.exists():
            backup=safe(base,'historical/p1_overlay_baseline/'+row['target'])
            if backup.exists() and sha(backup)!=sha(target):raise ValueError('Backup conflict; nothing was written')
        pending.append((row,source,target))
    # Every package/baseline/conflict check completes before the first write.
    for row,source,target in pending:
        if target.exists():
            backup=safe(base,'historical/p1_overlay_baseline/'+row['target'])
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists():shutil.copy2(target,backup)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    print(json.dumps({'installed_files':len(pending),'baseline_backups':'historical/p1_overlay_baseline',
        'A2':'NO-GO','P1':'BLOCKED_UNVERIFIED_PHYSICAL_HOLD','execution_authorized':False},indent=2))


if __name__=='__main__':main()
