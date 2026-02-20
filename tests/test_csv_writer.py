from pathlib import Path

from yahoo_crawler.domain.models import EquityQuote
from yahoo_crawler.output.csv_writer import CsvWriter


def test_csv_writer_generates_expected_file(tmp_path: Path) -> None:
    output_file = tmp_path / "equities.csv"
    records = [
        EquityQuote(symbol="AMX.BA", name="America Movil, S.A.B. de C.V.", price="2089.00"),
        EquityQuote(symbol="NOKA.BA", name="Nokia Corporation", price="557.50"),
    ]

    CsvWriter.write(str(output_file), records)

    content = output_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]

    assert lines[0] == '"symbol","name","price"'
    assert lines[1] == '"AMX.BA","America Movil, S.A.B. de C.V.","2089.00"'
    assert lines[2] == '"NOKA.BA","Nokia Corporation","557.50"'
