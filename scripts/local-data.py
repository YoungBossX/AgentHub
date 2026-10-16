"""Run with the existing project interpreter; no dependency installation."""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
from app.local_data import DataMaintenanceError, restore, snapshot, verify_snapshot
from app.local_data_cleanup import apply_cleanup, cleanup_preview, storage_inventory
from app.maintenance_lease import MaintenanceBusy


def main():
    parser = argparse.ArgumentParser(description="Offline local SQLite/Git snapshot and restore rehearsal")
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("snapshot")
    backup.add_argument("--repo", type=Path, required=True)
    backup.add_argument("--database", type=Path, required=True)
    backup.add_argument("--destination", type=Path, required=True)
    backup.add_argument("--api-port", type=int, default=8000)
    verify = sub.add_parser("verify")
    verify.add_argument("--snapshot", type=Path, required=True)
    recover = sub.add_parser("restore")
    recover.add_argument("--snapshot", type=Path, required=True)
    recover.add_argument("--destination", type=Path, required=True)
    recover.add_argument("--original-paths", action="store_true")
    recover.add_argument("--confirm-id")
    for name in ("inventory", "cleanup-preview", "cleanup-apply"):
        command = sub.add_parser(name)
        command.add_argument("--repo", type=Path, required=True)
        command.add_argument("--database", type=Path, required=True)
        command.add_argument("--api-port", type=int, default=8000)
        if name == "cleanup-preview":
            command.add_argument("--output", type=Path, required=True)
        if name == "cleanup-apply":
            command.add_argument("--plan", type=Path, required=True)
            command.add_argument("--confirm-id", required=True)
    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            result = snapshot(args.repo, args.database, args.destination, api_port=args.api_port)
        elif args.command == "verify":
            manifest = verify_snapshot(args.snapshot)
            result = {"state": "verified", "snapshotId": manifest["snapshotId"], "files": len(manifest["files"])}
        elif args.command == "restore":
            result = restore(args.snapshot, args.destination, original_paths=args.original_paths, confirm_id=args.confirm_id)
        elif args.command == "inventory":
            result = storage_inventory(args.repo, args.database, api_port=args.api_port)
        elif args.command == "cleanup-preview":
            from app.local_data import canonical, write_json
            result = cleanup_preview(args.repo, args.database, api_port=args.api_port)
            path = canonical(args.output)
            if path.is_relative_to(canonical(args.repo)):
                raise DataMaintenanceError("Save the preview to a new external file.")
            write_json(path, result)
        else:
            from app.local_data import regular
            info = regular(args.plan)
            if info.st_size > 32 * 1024**2:
                raise DataMaintenanceError("Cleanup plan exceeds size limit.")
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            result = apply_cleanup(args.repo, args.database, plan, confirm_id=args.confirm_id, api_port=args.api_port)
    except (DataMaintenanceError, MaintenanceBusy, OSError, ValueError) as exc:
        print(json.dumps({"state": "refused", "detail": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
