"""tools/ctl.py against the C library on the PC (--sim)."""
import ctl as client


def test_get_set_list_and_exit_codes(capsys):
    assert client.main(["--sim", "get", "tone_mid_hz"]) == 0
    assert capsys.readouterr().out.strip() == "ok tone_mid_hz 1000"
    assert client.main(["--sim", "set", "nosuch", "1"]) == 1
    assert capsys.readouterr().out.strip() == "err 3 unknown parameter"
    assert client.main(["--sim", "list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("100 in1_trim_db dB") and lines[-1].startswith("ok list ")
    assert client.main(["--sim", "raw", "preset list"]) == 0
    assert capsys.readouterr().out.strip() == "ok preset list 0"
