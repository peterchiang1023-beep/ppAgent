"""通用銷售 AI Agent — 命令列介面。

範例：
    python main.py research   --profile profiles/example.yaml --market CZ
    python main.py compliance --profile profiles/example.yaml --market DE
    python main.py budget
    python main.py drafts list
    python main.py drafts approve <草稿編號> --note "確認內容無誤"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from rich.console import Console
from rich.table import Table

from sales_agent.config import ConfigError, load_settings
from sales_agent.core.budget import BudgetExceeded, BudgetTracker
from sales_agent.logging_setup import log_action, setup_logging
from sales_agent.profiles.loader import ProfileError, load_profile

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="通用銷售 AI Agent（第一階段：research / compliance）")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (("research", "選品研究報告"), ("compliance", "市場通路與法規報告")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--profile", required=True, help="產品設定檔 YAML 路徑")
        p.add_argument("--market", required=True, help="目標國家 ISO 國碼，例如 CZ、DE")

    sub.add_parser("budget", help="查看今日預算與呼叫次數")

    d = sub.add_parser("drafts", help="草稿佇列（人工確認對外動作）")
    dsub = d.add_subparsers(dest="drafts_cmd", required=True)
    ls = dsub.add_parser("list", help="列出草稿")
    ls.add_argument("--status", choices=["pending", "approved", "rejected"])
    show = dsub.add_parser("show", help="顯示草稿內容")
    show.add_argument("draft_id")
    for cmd in ("approve", "reject"):
        p = dsub.add_parser(cmd, help="核准草稿" if cmd == "approve" else "退回草稿")
        p.add_argument("draft_id")
        p.add_argument("--note", default="")
    return parser


async def run_agent_task(args, settings) -> int:
    from sales_agent.core.supervisor import Supervisor
    from sales_agent.core.tasks import TASKS

    settings.require_api_key()
    profile = load_profile(args.profile)
    market = args.market.strip().upper()
    budget = BudgetTracker(settings.logs_dir, settings.daily_budget_usd, settings.daily_tool_call_limit)
    supervisor = Supervisor(settings, profile, budget, console)
    result = await supervisor.run(TASKS[args.command](profile, market), task_name=f"{args.command}:{market}")

    console.rule("執行結果")
    console.print(f"成功：{result.success}｜回合：{result.num_turns}｜本次成本：{result.cost_usd:.4f} USD")
    if result.reports:
        for path in result.reports:
            console.print(f"[bold green]📄 報告：{path}[/bold green]")
    else:
        console.print("[yellow]本次沒有產出報告檔[/yellow]")
    if result.stopped_reason:
        console.print(f"[bold red]⚠ 停止原因：{result.stopped_reason}[/bold red]")
    status = budget.status()
    console.print(
        f"今日累計：{status['cost_usd']}/{status['daily_budget_usd']} USD，"
        f"工具呼叫 {status['tool_calls']}/{status['daily_tool_call_limit']} 次"
    )
    return 0 if result.success and result.reports else 1


def handle_drafts(args, settings) -> int:
    from sales_agent.tools.draft_tool import DraftQueue

    queue = DraftQueue(settings.drafts_dir)
    if args.drafts_cmd == "list":
        table = Table("編號", "類型", "通路", "狀態", "摘要")
        for d in queue.list(args.status):
            table.add_row(d.id, d.action_type, d.channel, d.status, d.summary[:60])
        console.print(table)
    elif args.drafts_cmd == "show":
        console.print_json(json.dumps(queue.get(args.draft_id).__dict__, ensure_ascii=False))
    else:
        status = "approved" if args.drafts_cmd == "approve" else "rejected"
        d = queue.set_status(args.draft_id, status, args.note)
        console.print(f"草稿 {d.id} 已標記為 {d.status}。")
        if status == "approved":
            console.print("[yellow]第一階段尚未實作執行器，核准後不會實際寄信／上架／發文。[/yellow]")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    setup_logging(settings.logs_dir)
    log_action("cli", argv=sys.argv[1:] if argv is None else argv)
    try:
        if args.command in ("research", "compliance"):
            return asyncio.run(run_agent_task(args, settings))
        if args.command == "budget":
            b = BudgetTracker(settings.logs_dir, settings.daily_budget_usd, settings.daily_tool_call_limit)
            console.print_json(json.dumps(b.status(), ensure_ascii=False))
            return 0
        if args.command == "drafts":
            return handle_drafts(args, settings)
    except BudgetExceeded as exc:
        console.print(f"[bold red]🛑 預算上限：{exc}[/bold red]")
        return 2
    except (ConfigError, ProfileError, FileNotFoundError, ValueError) as exc:
        console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1
    except KeyboardInterrupt:
        console.print("[yellow]已中斷[/yellow]")
        return 130
    return 1


if __name__ == "__main__":
    sys.exit(main())
