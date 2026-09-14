import json

from mci_client.models import NodeState, ReconciliationReport
from mci_client.recorder import RecordWriter


def test_record_writer_creates_file_and_parent(tmp_path):

    path = tmp_path / "nested" / "dir" / "records.jsonl"
    writer = RecordWriter(str(path))

    report = ReconciliationReport(
        group_id="g1",
        state=NodeState.EXISTS,
        used_rounds=2,
        converged=True,
        failures=[],
    )
    writer.write_record(report)

    assert path.exists()
    content = path.read_text().strip()
    record = json.loads(content)
    assert record["group_id"] == "g1"
    assert record["state"] == "exists"
    assert record["used_rounds"] == 2
    assert record["converged"] is True
    assert "timestamp" in record


def test_record_writer_appends(tmp_path):

    path = tmp_path / "records.jsonl"
    writer = RecordWriter(str(path))

    for i in range(3):
        report = ReconciliationReport(
            group_id=f"g{i}",
            state=NodeState.EXISTS,
            used_rounds=1,
            converged=True,
        )
        writer.write_record(report)

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 3
    assert [json.loads(line)["group_id"] for line in lines] == ["g0", "g1", "g2"]