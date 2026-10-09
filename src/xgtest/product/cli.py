"""CLI adapter for the Test Product Layer: define and start a test mission."""
import json
from pathlib import Path

from xgtest.ai.controller import JobController
from xgtest.product.mission_service import MissionService


def register(commands, root):
    parser = commands.add_parser("mission", help="Define and start test missions (why/what to test)")
    parser.add_argument("--runtime-profile", type=Path)
    sub = parser.add_subparsers(dest="mission_command", required=True)
    create = sub.add_parser("create", help="Create a READY mission from a definition file")
    create.add_argument("--request", type=Path, required=True)
    sub.add_parser("list")
    for name in ("show", "start"):
        sub.add_parser(name).add_argument("mission_id")

    def handle(args):
        service = MissionService(root, JobController(root, args.runtime_profile))
        try:
            name = args.mission_command
            if name == "create":
                value = service.create(json.loads(args.request.read_text(encoding="utf-8-sig")))
            elif name == "list":
                value = {"items": service.store.list()}
            elif name == "show":
                value = service.view(args.mission_id)
            else:
                value = service.start(args.mission_id)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return 0
        except (OSError, ValueError) as error:
            print(json.dumps({"error": str(error)}, ensure_ascii=False))
            return 2
    parser.set_defaults(handler=handle)
