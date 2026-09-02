from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "gilbic_mobile" / "tool" / "bootstrap_platforms.ps1"


def test_flutter_bootstrap_generates_all_mvp_platforms() -> None:
    script = BOOTSTRAP.read_text(encoding="utf-8")

    assert "--platforms=android,ios,web,windows" in script
    assert 'Join-Path $ProjectRoot "test/widget_test.dart"' in script
    assert "Remove-Item -LiteralPath $GeneratedSampleTest -Force" in script
