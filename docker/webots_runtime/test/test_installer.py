import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from install_runtime import replace_once, supervisor_source


def test_unknown_vendor_source_is_rejected():
    with pytest.raises(RuntimeError, match='Upstream source changed'):
        replace_once('different API', 'expected', 'replacement')


def test_ambiguous_vendor_source_is_rejected():
    with pytest.raises(RuntimeError, match='Upstream source changed'):
        replace_once('expected expected', 'expected', 'replacement')
