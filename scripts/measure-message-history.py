"""Disposable, reproducible API history benchmark. Never opens product SQLite."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from sqlalchemy import event
from sqlmodel import SQLModel, Session as DbSession, create_engine
from app.models import Message, Session, Workspace
from app.routes.messages import read_session_messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=5000, choices=[1000, 5000])
    parser.add_argument("--mode", choices=["legacy", "page"], default="legacy")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="agenthub-history-measure-") as directory:
        engine = create_engine("sqlite:///" + (Path(directory) / "fixture.sqlite3").as_posix())
        SQLModel.metadata.create_all(engine)
        with DbSession(engine) as db:
            workspace = Workspace(name="History measurement", root_path="fixture", repo_url="local://fixture", default_branch="main")
            session = Session(workspace_id=workspace.id, title="History", bound_branch="main", worktree_path=str(Path(directory) / "worktree"))
            db.add_all([workspace, session]); db.commit()
            body = "历史消息验收：输入、过程和结果保持原始归属。\n" * 36
            rows = [Message(id=f"benchmark-message-{index:06d}", session_id=session.id, sender_type="user", content_md=f"{index}\n{body}") for index in range(args.count)]
            db.add_all(rows); db.commit(); sid = session.id
            db.expunge_all()
            statements = []
            def record(*a): statements.append(a[2].split()[0])
            event.listen(engine, "before_cursor_execute", record)
            tracemalloc.start()
            start = time.perf_counter()
            if args.mode == "legacy":
                response = read_session_messages(sid, db)
                payload = [row.model_dump(mode="json", by_alias=True) for row in response]
                returned = len(payload)
            else:
                from app.routes.message_history import read_message_page
                payload = read_message_page(sid, limit=80, before=None, after=None, around=None, db=db)
                returned = len(payload["messages"])
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            elapsed = (time.perf_counter() - start) * 1000
            _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
            event.remove(engine, "before_cursor_execute", record)
            print(json.dumps({"mode": args.mode, "fixtureMessages": args.count, "fixtureBodyCharacters": len(body),
                "fixtureBodySha256": hashlib.sha256(body.encode()).hexdigest(), "returnedMessages": returned,
                "responseBytes": len(encoded), "elapsedMsWithTracemalloc": round(elapsed, 2), "peakPythonBytes": peak,
                "sqlStatements": len(statements), "scope": "One isolated local API read/serialization; Python allocation tracing enabled; not Provider latency or a production benchmark"}))
        engine.dispose()


if __name__ == "__main__":
    main()
