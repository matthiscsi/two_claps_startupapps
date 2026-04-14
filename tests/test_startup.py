import pytest
from src.startup_helper import format_bat_content, format_vbs_script

def test_format_bat_with_spaces():
    work_dir = "C:\\Path With Spaces"
    content = format_bat_content(work_dir)
    assert 'cd /d "C:\\Path With Spaces"' in content

def test_format_vbs_with_spaces():
    shortcut = "C:\\Startup\\My Shortcut.lnk"
    target = "C:\\Program Files\\App.exe"
    work = "C:\\Program Files"

    script = format_vbs_script(shortcut, target, work)
    assert f'sLinkFile = "{shortcut}"' in script
    assert f'oLink.TargetPath = "{target}"' in script
    assert f'oLink.WorkingDirectory = "{work}"' in script

def test_format_vbs_with_quotes():
    # Extreme edge case: path containing double quotes
    shortcut = 'C:\\"Path"\\Lnk.lnk'
    target = 'C:\\"Target"\\App.exe'
    work = 'C:\\"Work"'

    script = format_vbs_script(shortcut, target, work)
    # Quotes should be doubled in VBScript
    assert 'sLinkFile = "C:\\""Path""\\Lnk.lnk"' in script
    assert 'oLink.TargetPath = "C:\\""Target""\\App.exe"' in script
    assert 'oLink.WorkingDirectory = "C:\\""Work"""' in script
