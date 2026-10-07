#!/usr/bin/env python3
"""Apply the AI DJ provider and guest-page patch to pinned MA source checkouts."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--server', type=Path, required=True)
parser.add_argument('--frontend', type=Path, required=True)
args = parser.parse_args()
refs = json.loads((ROOT / 'upstream.json').read_text())
for name, checkout in [('server', args.server), ('frontend', args.frontend)]:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
    if head != refs[name]:
        raise SystemExit(f'{name}: unsupported revision {head}; expected {refs[name]}. No files changed.')
provider = args.server / 'music_assistant/providers/ai_dj'
component = args.frontend / 'src/components/party/PartyAiSearch.vue'
if provider.exists() or component.exists():
    raise SystemExit('AI DJ already exists; refusing to overwrite it.')
subprocess.run(['git', 'apply', '--check', str(ROOT / 'frontend.patch')], cwd=args.frontend, check=True)
shutil.copytree(ROOT / 'provider', provider, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
shutil.copyfile(ROOT / 'frontend/PartyAiSearch.vue', component)
subprocess.run(['git', 'apply', str(ROOT / 'frontend.patch')], cwd=args.frontend, check=True)
print('Provider and existing Party guest page patched. Build and test MA before deploying.')
