"""Download pinned primary-source bytes with TLS verification retained."""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
GAZ = '24d85ce4e648e2e894c832bfeee9b16711eb1a1a'
ROS = 'ddd2fffd9de44b02ad15b4bbb2bfa2cec4d60d98'
SOURCES = {
    'DynPars2VREP.m': ('marcocognetti/FrankaEmikaPandaDynModel', GAZ, 'matlab/ConvertDynPars2VREP/DynPars2VREP.m'),
    'get_FrictionTorque.m': ('marcocognetti/FrankaEmikaPandaDynModel', GAZ, 'matlab/dyn_model_panda/get_FrictionTorque.m'),
    'supplement.pdf': ('marcocognetti/FrankaEmikaPandaDynModel', GAZ, 'pdf/RA-L_2019_PandaDynIdent_SUPPLEMENTARY_MATERIAL.pdf'),
    'franka_arm.xacro': ('frankarobotics/franka_ros', ROS, 'franka_description/robots/common/franka_arm.xacro'),
    'utils.xacro': ('frankarobotics/franka_ros', ROS, 'franka_description/robots/common/utils.xacro'),
    'gaz_README.txt': ('marcocognetti/FrankaEmikaPandaDynModel', GAZ, 'README.txt'),
    'gaz_LICENSE': ('marcocognetti/FrankaEmikaPandaDynModel', GAZ, 'LICENSE'),
    'franka_ros_LICENSE': ('frankarobotics/franka_ros', ROS, 'LICENSE'),
    'franka_ros_NOTICE': ('frankarobotics/franka_ros', ROS, 'NOTICE'),
}


def main():
    records = []
    for name, (repo, commit, path) in SOURCES.items():
        url = f'https://raw.githubusercontent.com/{repo}/{commit}/{path}'
        output = ROOT / 'sources' / name
        temp = output.with_suffix(output.suffix + '.download')
        args = ['curl', '--fail', '--location', '--retry', '1', '--max-time', '60', '--silent', '--show-error', url, '--output', str(temp)]
        result = subprocess.run(args, capture_output=True, text=True)
        row = {'file': name, 'repository': repo, 'commit': commit, 'path': path, 'url': url,
               'retrieved_utc': datetime.now(timezone.utc).isoformat(), 'command': args,
               'exit_code': result.returncode}
        if result.returncode == 0:
            data = temp.read_bytes()
            temp.replace(output)
            row.update(status='DOWNLOADED_PINNED_URL', bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                       git_blob_sha1=hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest())
        else:
            row.update(status='BLOCKED', error=result.stderr)
            temp.unlink(missing_ok=True)
        records.append(row)
        print(name, row['status'], row.get('sha256', row.get('error')))
    report = ROOT / 'reports/source_downloads.json'
    report.write_text(json.dumps(records, indent=2) + '\n')
    if any(r['exit_code'] != 0 for r in records):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
