#!/usr/bin/env python3
"""pcurate: A utility for curating Arch Linux/macOS/Debian software package lists."""

__version__ = '0.3.0'

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List

class PackageManager:
    """Abstract base class for package manager drivers."""
    def get_installed(self) -> Dict[str, Dict[str, Any]]:
        """Return dict of package_name -> {'description': str, 'native': int}."""
        return {}
    
    def resolve_groups(self, names: List[str]) -> List[str]:
        """Resolve package group names to individual package names."""
        return names

class PacmanManager(PackageManager):
    """Arch Linux package manager driver."""
    def get_installed(self) -> Dict[str, Dict[str, Any]]:
        pkgs = {}
        try:
            out = subprocess.check_output(['pacman', '-Qei'], text=True)
            status, native_out = subprocess.getstatusoutput('pacman -Qqen')
            native = set(native_out.splitlines()) if status == 0 else set()
            current = None
            for line in out.splitlines():
                if line.startswith('Name'):
                    current = line.split(': ', 1)[1].strip()
                elif line.startswith('Description') and current:
                    desc = line.split(': ', 1)[1].strip()
                    pkgs[current] = {'description': desc, 'native': 1 if current in native else 0}
                    current = None
        except Exception:
            pass
        return pkgs

    def resolve_groups(self, names: List[str]) -> List[str]:
        if not names:
            return []
        try:
            res = subprocess.run(['pacman', '-Sgq'] + names, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return res.stdout.splitlines()
        except Exception:
            pass
        return []

class BrewManager(PackageManager):
    """macOS Homebrew package manager driver."""
    def get_installed(self) -> Dict[str, Dict[str, Any]]:
        pkgs = {}
        try:
            out = subprocess.check_output(['brew', 'info', '--json=v2', '--installed'], text=True)
            data = json.loads(out)
            for f in data.get('formulae', []):
                pkgs[f['name']] = {'description': f.get('desc', ''), 'native': 1}
            for c in data.get('casks', []):
                pkgs[c['token']] = {'description': c.get('desc', '') or '', 'native': 0}
        except Exception:
            pass
        return pkgs

class AptManager(PackageManager):
    """Debian/Ubuntu APT package manager driver."""
    def get_installed(self) -> Dict[str, Dict[str, Any]]:
        pkgs = {}
        try:
            res = subprocess.run(['apt-mark', 'showmanual'], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                manual = [p.strip() for p in res.stdout.splitlines() if p.strip()]
                if manual:
                    res_query = subprocess.run(
                        ['dpkg-query', '-W', '-f=${Package}\t${Description}\n'] + manual,
                        capture_output=True, text=True, check=False
                    )
                    for line in res_query.stdout.splitlines():
                        if '\t' in line:
                            n, d = line.split('\t', 1)
                            pkgs[n] = {'description': d.strip(), 'native': 1}
        except Exception:
            pass
        return pkgs

class Pcurate:
    """Core logic runner for package curation."""
    def __init__(self, config_dir: str = None, pm: PackageManager = None) -> None:
        if not config_dir:
            xdg = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
            config_dir = os.path.join(xdg, 'pcurate')
        self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)
        self.json_path = os.path.join(self.config_dir, 'curated.json')
        self.filter_path = os.path.join(self.config_dir, 'filter.txt')
        self.pm = pm or self.detect_pm()

    def detect_pm(self) -> PackageManager:
        if shutil.which('pacman'):
            return PacmanManager()
        if shutil.which('brew'):
            return BrewManager()
        if shutil.which('dpkg-query') and shutil.which('apt-mark'):
            return AptManager()
        return PackageManager()

    def load_curated(self) -> Dict[str, Dict[str, str]]:
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r') as f:
                    return json.load(f).get('packages', {})
            except Exception:
                pass
        return {}

    def save_curated(self, curated: dict) -> None:
        try:
            with open(self.json_path, 'w') as f:
                json.dump({'packages': curated}, f, indent=2)
        except Exception as e:
            print(f"Error saving curated list: {e}", file=sys.stderr)

    def load_filters(self) -> List[str]:
        filters = []
        if os.path.exists(self.filter_path):
            try:
                with open(self.filter_path, 'r') as f:
                    for line in f:
                        line = line.split('#', 1)[0].strip()
                        if line:
                            filters.extend(line.split())
            except Exception:
                pass
        return filters

    def run(self, args) -> None:
        curated = self.load_curated()

        # Handle Package-Specific Queries/Mutations
        if args.PACKAGE_NAME:
            name = args.PACKAGE_NAME
            if args.set:
                curated[name] = {
                    'tag': args.tag or (curated.get(name, {}).get('tag') or ''),
                    'description': args.desc or (curated.get(name, {}).get('description') or '')
                }
                self.save_curated(curated)
            elif args.unset:
                if name in curated:
                    del curated[name]
                    self.save_curated(curated)
            else:
                # Display package info in CSV format using stdlib csv writer
                installed = self.pm.get_installed()
                writer = csv.writer(sys.stdout)
                if name in curated:
                    tag = curated[name].get('tag', '')
                    desc = curated[name].get('description', '')
                    native = installed.get(name, {}).get('native', 0)
                    native_str = 'native' if native else 'foreign'
                    writer.writerow([name, 'curated', tag, desc, native_str])
                elif name in installed:
                    desc = installed[name].get('description', '')
                    native = installed[name].get('native', 0)
                    native_str = 'native' if native else 'foreign'
                    writer.writerow([name, 'regular', '', desc, native_str])
                else:
                    print(f"package not explicitly installed ({name})", file=sys.stderr)
                    sys.exit(1)
            return

        # Handle List Queries (-c, -r, -m)
        installed = self.pm.get_installed()
        pkgs = {}

        if args.curated:
            for name, info in curated.items():
                native = installed.get(name, {}).get('native', 0)
                pkgs[name] = {
                    'tag': info.get('tag', ''),
                    'description': info.get('description', ''),
                    'native': native,
                    'status': 'curated'
                }
        elif args.regular:
            filters = set(self.load_filters())
            group_pkgs = set(self.pm.resolve_groups(list(filters)))
            all_filters = filters | group_pkgs
            for name, info in installed.items():
                if name not in curated and name not in all_filters:
                    pkgs[name] = {
                        'tag': '',
                        'description': info.get('description', ''),
                        'native': info.get('native', 0),
                        'status': 'regular'
                    }
        elif args.missing:
            for name, info in curated.items():
                if name not in installed:
                    pkgs[name] = {
                        'tag': info.get('tag', ''),
                        'description': info.get('description', ''),
                        'native': 0,
                        'status': 'curated'
                    }

        # Filter by Native/Foreign status
        if args.native:
            pkgs = {k: v for k, v in pkgs.items() if v['native'] == 1}
        elif args.foreign:
            pkgs = {k: v for k, v in pkgs.items() if v['native'] == 0}

        # Format and Output Results
        if args.verbose:
            writer = csv.writer(sys.stdout)
            writer.writerow(["name", "status", "tag", "description", "native"])
            for name in sorted(pkgs.keys()):
                info = pkgs[name]
                native_str = "native" if info['native'] == 1 else "foreign"
                writer.writerow([name, info['status'], info['tag'], info['description'], native_str])
        else:
            for name in sorted(pkgs.keys()):
                print(name)

def main() -> None:
    parser = argparse.ArgumentParser(description="pcurate: A tool to organize and curate package lists.")
    parser.add_argument('--version', action='version', version='pcurate version ' + __version__)
    parser.add_argument('PACKAGE_NAME', nargs='?', help="Package name to query or set/unset curated status")
    parser.add_argument('-u', '--unset', action='store_true', help="Unset package curated status")
    parser.add_argument('-s', '--set', action='store_true', help="Set package curated status")
    parser.add_argument('-t', '--tag', help="Set package tag")
    parser.add_argument('-d', '--desc', help="Set package description")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-c', '--curated', action='store_true', help="Display all curated packages")
    group.add_argument('-r', '--regular', action='store_true', help="Display packages not curated")
    group.add_argument('-m', '--missing', action='store_true', help="Display missing curated packages")

    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument('-n', '--native', action='store_true', help="Limit display to native packages")
    filter_group.add_argument('-f', '--foreign', action='store_true', help="Limit display to foreign packages")

    parser.add_argument('-v', '--verbose', action='store_true', help="Display additional info in CSV format")

    args = parser.parse_args()
    if not args.PACKAGE_NAME and not (args.curated or args.regular or args.missing):
        parser.print_usage()
        sys.exit(1)

    Pcurate().run(args)

if __name__ == '__main__':
    main()
