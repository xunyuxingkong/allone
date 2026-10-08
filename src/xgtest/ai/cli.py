"""CLI adapter for external agents; no hosted model credentials required."""
import json
from pathlib import Path
from xgtest.ai.controller import JobController


def register(commands, root):
    parser = commands.add_parser("ai", help="External-agent controlled test jobs")
    parser.add_argument("--runtime-profile", type=Path)
    sub = parser.add_subparsers(dest="ai_command", required=True)
    run = sub.add_parser("run", help="Create a job after the external agent resolves the intent")
    run.add_argument("goal")
    run.add_argument("--intent", required=True, choices=("query.full_test", "query.join.verify", "query.status"))
    sub.add_parser("list")
    for name in ("status", "resume", "act", "context", "annotate"):
        item = sub.add_parser(name)
        item.add_argument("job_id")
        if name in {"resume", "annotate"}: item.add_argument("--revision", type=int, required=True)
        if name in {"act", "annotate"}: item.add_argument("--request", type=Path, required=True)
        if name == "context": item.add_argument("case_id")
    def handle(args):
        controller = JobController(root, args.runtime_profile)
        try:
            name = args.ai_command
            if name == "run": value = controller.create(args.goal, {"intent": args.intent})
            elif name == "list": value = {"items": controller.store.list()}
            elif name == "status": value = controller.status(args.job_id)
            elif name == "resume": value = controller.resume(args.job_id, args.revision)
            elif name == "context": value = controller.review_context(args.job_id, args.case_id)
            else:
                request = json.loads(args.request.read_text(encoding="utf-8-sig"))
                value = controller.execute(args.job_id, request) if name == "act" else controller.annotate(args.job_id, args.revision, **request)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return 0
        except (OSError, ValueError) as error:
            print(json.dumps({"error": str(error)}, ensure_ascii=False))
            return 2
    parser.set_defaults(handler=handle)
