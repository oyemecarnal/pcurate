"""Test pcurate module with pytest."""

import csv
import io
import json
import os
import sys
import pytest
from pcurate import Pcurate, PackageManager

class MockPackageManager(PackageManager):
    def get_installed(self) -> dict:
        return {
            'base': {'description': 'base_description', 'native': 1},
            'comma_pkg': {'description': 'description, with, commas', 'native': 1},
            'filter_one': {'description': 'desc', 'native': 1},
            'filter_two': {'description': 'desc', 'native': 1},
            'filter_three': {'description': 'desc', 'native': 1},
            'pkg_0': {'description': 'desc_0', 'native': 1},
            'pkg_1': {'description': 'desc_1', 'native': 1},
            'pkg_2': {'description': 'desc_2', 'native': 1},
            'pkg_3': {'description': 'desc_3', 'native': 1},
            'pkg_4': {'description': 'desc_4', 'native': 1},
            'pkg_5': {'description': 'desc_5', 'native': 1},
        }

    def resolve_groups(self, names: list) -> list:
        if 'group_one' in names:
            return ['filter_one', 'filter_three']
        return []

@pytest.fixture
def temp_config(tmp_path):
    """Init a temp config directory."""
    return str(tmp_path)

class DummyArgs:
    def __init__(self, **kwargs):
        self.PACKAGE_NAME = kwargs.get('PACKAGE_NAME', None)
        self.unset = kwargs.get('unset', False)
        self.set = kwargs.get('set', False)
        self.tag = kwargs.get('tag', None)
        self.desc = kwargs.get('desc', None)
        self.curated = kwargs.get('curated', False)
        self.regular = kwargs.get('regular', False)
        self.missing = kwargs.get('missing', False)
        self.native = kwargs.get('native', False)
        self.foreign = kwargs.get('foreign', False)
        self.verbose = kwargs.get('verbose', False)

def test_package_set(temp_config) -> None:
    """Test setting a package curated status."""
    p = Pcurate(temp_config, MockPackageManager())
    
    # Curate base package
    args = DummyArgs(PACKAGE_NAME='base', set=True, tag='test_tag', desc='test_description')
    p.run(args)
    
    curated = p.load_curated()
    assert 'base' in curated
    assert curated['base']['tag'] == 'test_tag'
    assert curated['base']['description'] == 'test_description'

def test_package_unset(temp_config) -> None:
    """Test unsetting a package curated status."""
    p = Pcurate(temp_config, MockPackageManager())
    
    # Pre-populate curated list
    curated = {'base': {'tag': 'test_tag', 'description': 'test_description'}}
    p.save_curated(curated)
    
    # Unset base package
    args = DummyArgs(PACKAGE_NAME='base', unset=True)
    p.run(args)
    
    assert 'base' not in p.load_curated()

def test_regular_list(temp_config, capsys) -> None:
    """Test listing regular packages."""
    p = Pcurate(temp_config, MockPackageManager())
    args = DummyArgs(regular=True)
    p.run(args)
    
    captured = capsys.readouterr()
    lines = captured.out.strip().split('\n')
    assert len(lines) == 11  # 11 packages in mock
    assert 'base' in lines

def test_filtering(temp_config, capsys) -> None:
    """Test package exclusion via filter.txt."""
    p = Pcurate(temp_config, MockPackageManager())
    
    # Write filters
    with open(p.filter_path, 'w') as f:
        f.write('filter_one\nfilter_three\n')
        
    args = DummyArgs(regular=True)
    p.run(args)
    
    captured = capsys.readouterr()
    lines = captured.out.strip().split('\n')
    assert 'filter_one' not in lines
    assert 'filter_three' not in lines
    assert 'filter_two' in lines

def test_group_filtering(temp_config, capsys) -> None:
    """Test package group expansion in filter.txt."""
    p = Pcurate(temp_config, MockPackageManager())
    
    # Write group filter
    with open(p.filter_path, 'w') as f:
        f.write('group_one\n')
        
    args = DummyArgs(regular=True)
    p.run(args)
    
    captured = capsys.readouterr()
    lines = captured.out.strip().split('\n')
    assert 'filter_one' not in lines
    assert 'filter_three' not in lines
    assert 'filter_two' in lines

def test_missing(temp_config, capsys) -> None:
    """Test detection of missing curated packages."""
    p = Pcurate(temp_config, MockPackageManager())
    
    curated = {
        'base': {'tag': 'tag', 'description': 'desc'},  # Installed
        'missing_pkg': {'tag': 'tag', 'description': 'desc'}  # Not installed
    }
    p.save_curated(curated)
    
    args = DummyArgs(missing=True)
    p.run(args)
    
    captured = capsys.readouterr()
    lines = captured.out.strip().split('\n')
    assert 'missing_pkg' in lines
    assert 'base' not in lines

def test_csv_quoting(temp_config, capsys) -> None:
    """Test that CSV output is formatted robustly and description commas are escaped."""
    p = Pcurate(temp_config, MockPackageManager())
    
    # Run in verbose mode
    args = DummyArgs(regular=True, verbose=True)
    p.run(args)
    
    captured = capsys.readouterr()
    output = captured.out.strip()
    
    # Parse output using csv module
    reader = csv.reader(io.StringIO(output))
    rows = list(reader)
    
    header = rows[0]
    assert header == ["name", "status", "tag", "description", "native"]
    
    # Find comma_pkg row
    comma_pkg_row = next((row for row in rows if row[0] == 'comma_pkg'), None)
    assert comma_pkg_row is not None
    assert comma_pkg_row[1] == 'regular'
    assert comma_pkg_row[3] == 'description, with, commas'
    assert comma_pkg_row[4] == 'native'
