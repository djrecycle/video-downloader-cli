from __future__ import annotations

import argparse
import concurrent.futures
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich import box
from yt_dlp import YoutubeDL


DEFAULT_OUTPUT_TEMPLATE = "%(title).200B [%(id)s].%(ext)s"
DEFAULT_VIDEO_FORMAT = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"
DEFAULT_DOWNLOAD_DIR = Path("downloads")

console = Console(highlight=False)


class QuietLogger:
    def debug(self, message: str) -> None:
        return None

    def warning(self, message: str) -> None:
        return None

    def error(self, message: str) -> None:
        return None


@dataclass(frozen=True)
class DownloadOptions:
    output_dir: Path
    audio_only: bool
    format_selector: str | None
    archive_file: Path | None
    retries: int
    dry_run: bool


@dataclass(frozen=True)
class DownloadResult:
    url: str
    ok: bool
    message: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="video-dl",
        description="Download video dari internet. Fokus awal: YouTube.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "urls",
        nargs="*",
        help="URL video/playlist. Pakai '-' untuk membaca URL dari stdin.",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Buka mode interaktif dengan menu terminal.",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        help="File teks berisi daftar URL, satu URL per baris.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_DOWNLOAD_DIR,
        help="Folder tujuan download. Default: ./downloads",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=1,
        help="Jumlah download paralel. Default: 1",
    )
    parser.add_argument(
        "--format",
        dest="format_selector",
        help="Format yt-dlp, misalnya 'bestvideo+bestaudio/best' atau 'best'.",
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Download audio saja dan ekstrak ke mp3 jika ffmpeg tersedia.",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        help="Simpan riwayat URL yang sudah didownload agar tidak diulang.",
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Izinkan download playlist. Default hanya video tunggal.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Jumlah percobaan ulang saat gagal. Default: 3",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Cek URL dan tampilkan judul tanpa mendownload.",
    )
    return parser.parse_args(argv)


def print_help() -> None:
    print_header()

    commands = Table(box=box.SIMPLE_HEAD, show_header=False, padding=(0, 1))
    commands.add_column(style="bold green")
    commands.add_column()
    commands.add_row("Interaktif", "./video-dl")
    commands.add_row("Banyak URL", './video-dl "URL_1" "URL_2"')
    commands.add_row("Dari file", "./video-dl --file links.txt")
    commands.add_row("Audio", "./video-dl --audio-only --file links.txt")
    commands.add_row("Paralel", "./video-dl --workers 3 --file links.txt")
    console.print(Panel(commands, title="[bold]🚀 Perintah[/bold]", border_style="cyan", box=box.ROUNDED))

    options_table = Table(box=box.SIMPLE_HEAD, show_header=False, padding=(0, 1))
    options_table.add_column(style="bold green")
    options_table.add_column(style="dim")
    options = [
        ("-i, --interactive", "buka menu interaktif"),
        ("-f, --file FILE", "ambil link dari file teks"),
        ("-o, --output DIR", "folder tujuan download"),
        ("-w, --workers N", "jumlah download paralel"),
        ("--format FORMAT", "format yt-dlp custom"),
        ("--audio-only", "download audio saja"),
        ("--archive FILE", "catat video yang sudah didownload"),
        ("--playlist", "izinkan download playlist"),
        ("--retries N", "jumlah percobaan ulang"),
        ("--dry-run", "cek judul tanpa download"),
        ("-h, --help", "tampilkan bantuan ini"),
    ]
    for name, description in options:
        options_table.add_row(name, description)
    console.print(Panel(options_table, title="[bold]⚙️  Opsi[/bold]", border_style="cyan", box=box.ROUNDED))


def print_header() -> None:
    banner = (
        "[bold cyan]🎬 YOUTUBE DOWNLOADER[/bold cyan]\n"
        "[dim]Download banyak video dari terminal, ditenagai yt-dlp[/dim]"
    )
    console.print(Panel(Align.center(banner), box=box.DOUBLE, border_style="cyan", padding=(1, 4)))


def info_panel(title: str, rows: list[tuple[str, str]], border_style: str = "cyan") -> None:
    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    for label, value in rows:
        table.add_row(label, value)
    console.print(Panel(table, title=f"[bold]{title}[/bold]", border_style=border_style, box=box.ROUNDED))


def print_error(message: str) -> None:
    print_header()
    console.print(Panel(f"[yellow]{message}[/yellow]", title="[bold red]❌ GAGAL[/bold red]", border_style="red"))


def short_url(url: str, limit: int = 72) -> str:
    if len(url) <= limit:
        return url
    return f"{url[: limit - 3]}..."


def prompt_url_source() -> list[str]:
    console.print()
    console.print("[bold]📋 Sumber URL[/bold]")
    choice = Prompt.ask(
        "[bold blue]Mau download berapa URL?[/bold blue]",
        choices=["1", "banyak"],
        default="1",
    )
    if choice == "1":
        return prompt_single_url()
    return prompt_urls_from_file()


def prompt_single_url() -> list[str]:
    url = Prompt.ask("[bold blue]Tulis link video[/bold blue]").strip()
    return dedupe_urls(read_url_lines([url]))


def prompt_urls_from_file() -> list[str]:
    console.print("[dim]Tulis path file .txt berisi daftar URL, satu URL per baris.[/dim]")
    while True:
        raw_path = Prompt.ask("[bold blue]Path file URL[/bold blue]").strip()
        file_path = Path(raw_path).expanduser()
        if not file_path.is_file():
            console.print(f"[yellow]File tidak ditemukan: {file_path}[/yellow]")
            continue
        urls = dedupe_urls(read_url_lines(file_path.read_text(encoding="utf-8").splitlines()))
        if not urls:
            console.print(f"[yellow]File {file_path} tidak berisi URL yang valid.[/yellow]")
            continue
        return urls


def sanitize_subfolder(name: str) -> str:
    parts = [part for part in name.strip().split("/") if part not in ("", ".", "..")]
    return "/".join(parts)


def prompt_output_dir() -> Path:
    console.print(f"[dim]Default: file hasil download masuk ke folder '{DEFAULT_DOWNLOAD_DIR}/'.[/dim]")
    want_new_folder = Confirm.ask(
        f"[bold blue]Buat folder baru di dalam '{DEFAULT_DOWNLOAD_DIR}/'[/bold blue]", default=False
    )
    if not want_new_folder:
        return DEFAULT_DOWNLOAD_DIR

    while True:
        raw_name = Prompt.ask("[bold blue]Nama folder baru[/bold blue]")
        folder_name = sanitize_subfolder(raw_name)
        if not folder_name:
            console.print("[yellow]Nama folder tidak boleh kosong.[/yellow]")
            continue
        return DEFAULT_DOWNLOAD_DIR / folder_name


def run_interactive(defaults: argparse.Namespace) -> int:
    print_header()
    urls = prompt_url_source()
    if not urls:
        console.print("[bold red]Tidak ada URL yang dimasukkan.[/bold red]")
        return 2

    console.print()
    console.print("[bold]🛠️  Pengaturan download[/bold]")
    output_dir = prompt_output_dir()
    workers = IntPrompt.ask(
        "[bold blue]Jumlah download paralel (1-8)[/bold blue]", default=defaults.workers
    )
    workers = max(1, min(8, workers))
    audio_only = Confirm.ask("[bold blue]Audio saja[/bold blue]", default=defaults.audio_only)
    allow_playlist = Confirm.ask("[bold blue]Izinkan playlist[/bold blue]", default=defaults.playlist)
    use_archive = Confirm.ask(
        "[bold blue]Aktifkan arsip agar video yang sama tidak didownload ulang[/bold blue]", default=False
    )
    archive_file = Path("downloads/archive.txt") if use_archive else None
    if archive_file:
        archive_file = Path(Prompt.ask("[bold blue]File arsip[/bold blue]", default=str(archive_file))).expanduser()

    custom_format = Confirm.ask("[bold blue]Pakai format yt-dlp custom[/bold blue]", default=False)
    format_selector = None
    if custom_format:
        format_selector = Prompt.ask(
            "[bold blue]Format[/bold blue]", default=defaults.format_selector or "bestvideo*+bestaudio/best"
        )

    dry_run = Confirm.ask("[bold blue]Cek judul saja tanpa download[/bold blue]", default=defaults.dry_run)

    options = DownloadOptions(
        output_dir=output_dir,
        audio_only=audio_only,
        format_selector=format_selector,
        archive_file=archive_file,
        retries=defaults.retries,
        dry_run=dry_run,
    )

    console.print()
    info_panel(
        "📝 Ringkasan",
        [
            ("URL", str(len(urls))),
            ("Output", str(output_dir)),
            ("Worker", str(workers)),
            ("Mode", "🎧 audio" if audio_only else "🎥 video"),
            ("Playlist", "✅ ya" if allow_playlist else "❌ tidak"),
            ("Dry run", "✅ ya" if dry_run else "❌ tidak"),
            *([("Arsip", str(archive_file))] if archive_file else []),
        ],
        border_style="magenta",
    )

    if not Confirm.ask("[bold green]Mulai sekarang[/bold green]", default=True):
        console.print("[yellow]Dibatalkan.[/yellow]")
        return 0

    console.print()
    return run_downloads(
        urls=urls,
        options=options,
        allow_playlist=allow_playlist,
        workers=workers,
    )


def read_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []

    if args.file:
        urls.extend(read_url_lines(args.file.read_text(encoding="utf-8").splitlines()))

    for value in args.urls:
        if value == "-":
            urls.extend(read_url_lines(sys.stdin.read().splitlines()))
        else:
            urls.append(value.strip())

    return dedupe_urls(read_url_lines(urls))


def read_url_lines(lines: Iterable[str]) -> list[str]:
    urls: list[str] = []
    for line in lines:
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        urls.append(item)
    return urls


def dedupe_urls(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique.append(url)
    return unique


def build_ydl_options(
    options: DownloadOptions,
    allow_playlist: bool,
    progress_hook: Callable[[dict], None] | None = None,
) -> dict:
    output_template = str(options.output_dir / DEFAULT_OUTPUT_TEMPLATE)
    ydl_options: dict = {
        "outtmpl": output_template,
        "noplaylist": not allow_playlist,
        "retries": options.retries,
        "fragment_retries": options.retries,
        "continuedl": True,
        "ignoreerrors": False,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": QuietLogger(),
    }

    if options.format_selector:
        ydl_options["format"] = options.format_selector
    elif options.audio_only:
        ydl_options["format"] = "bestaudio/best"
    else:
        ydl_options["format"] = DEFAULT_VIDEO_FORMAT

    if options.archive_file:
        ydl_options["download_archive"] = str(options.archive_file)

    if options.audio_only:
        ydl_options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    if options.dry_run:
        ydl_options["skip_download"] = True
        ydl_options["simulate"] = True
    elif progress_hook:
        ydl_options["progress_hooks"] = [progress_hook]

    return ydl_options


def download_one(
    url: str,
    options: DownloadOptions,
    allow_playlist: bool,
    progress_hook: Callable[[dict], None] | None = None,
) -> DownloadResult:
    try:
        ydl_options = build_ydl_options(options, allow_playlist, progress_hook)
        with YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(url, download=not options.dry_run)
            title = info.get("title", "tanpa judul") if info else "tanpa judul"
            if options.dry_run:
                return DownloadResult(url=url, ok=True, message=f"Terdeteksi: {title}")
        return DownloadResult(url=url, ok=True, message=f"Selesai: {title}")
    except Exception as exc:  # yt-dlp raises multiple exception classes.
        return DownloadResult(url=url, ok=False, message=str(exc))


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.fields[label]}", justify="left"),
        BarColumn(bar_width=28),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )


class ProgressTracker:
    def __init__(self, progress: Progress) -> None:
        self.progress = progress
        self.lock = threading.Lock()
        self.task_ids: dict[str, TaskID] = {}

    def hook_for(self, url: str) -> Callable[[dict], None]:
        def hook(data: dict) -> None:
            status = data.get("status")
            with self.lock:
                task_id = self.task_ids.get(url)
                if task_id is None:
                    task_id = self.progress.add_task(
                        "download", label=f"⏳ {short_url(url, 40)}", total=None
                    )
                    self.task_ids[url] = task_id

            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                downloaded = data.get("downloaded_bytes") or 0
                self.progress.update(task_id, total=total, completed=downloaded)
            elif status == "finished":
                total = data.get("total_bytes") or data.get("downloaded_bytes") or 1
                self.progress.update(
                    task_id,
                    total=total,
                    completed=total,
                    label=f"🔧 {short_url(url, 40)} (memproses...)",
                )

        return hook


def run_downloads(
    urls: list[str],
    options: DownloadOptions,
    allow_playlist: bool,
    workers: int,
) -> int:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    if options.archive_file:
        options.archive_file.parent.mkdir(parents=True, exist_ok=True)

    print_header()
    info_panel(
        "📦 Sesi Download",
        [
            ("URL", str(len(urls))),
            ("Output", str(options.output_dir.resolve())),
            ("Worker", str(workers)),
            ("Mode", "🎧 audio" if options.audio_only else "🎥 video"),
            ("Playlist", "aktif" if allow_playlist else "nonaktif"),
            ("Dry run", "aktif" if options.dry_run else "nonaktif"),
        ],
    )
    console.print()

    if options.dry_run:
        failed = 0
        for index, url in enumerate(urls, start=1):
            console.print(f"[bold magenta][{index}/{len(urls)}][/bold magenta] [dim]{short_url(url)}[/dim]")
            result = download_one(url, options, allow_playlist, None)
            failed += report_result(result)
        print_final_summary(len(urls), failed)
        return 1 if failed else 0

    failed = 0
    with make_progress() as progress:
        tracker = ProgressTracker(progress)

        if workers == 1:
            for url in urls:
                result = download_one(url, options, allow_playlist, tracker.hook_for(url))
                failed += report_result(result, progress.console)
        else:
            console.print(f"[bold magenta]Menjalankan {len(urls)} download dengan {workers} worker...[/bold magenta]")
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_url = {
                    executor.submit(download_one, url, options, allow_playlist, tracker.hook_for(url)): url
                    for url in urls
                }
                for future in concurrent.futures.as_completed(future_to_url):
                    result = future.result()
                    failed += report_result(result, progress.console)

    print_final_summary(len(urls), failed)
    return 1 if failed else 0


def report_result(result: DownloadResult, out: Console | None = None) -> int:
    out = out or console
    icon = "[bold green]✅ OK[/bold green]" if result.ok else "[bold red]❌ GAGAL[/bold red]"
    out.print(f"{icon} {short_url(result.url)}")
    if result.message:
        style = "dim" if result.ok else "yellow"
        out.print(f"   [{style}]{result.message}[/{style}]")
    return 0 if result.ok else 1


def print_final_summary(total: int, failed: int) -> None:
    success = total - failed
    status = "[bold green]✅ selesai[/bold green]" if failed == 0 else "[bold yellow]⚠️  selesai dengan error[/bold yellow]"
    console.print()
    info_panel(
        "🏁 Hasil Akhir",
        [
            ("Berhasil", f"[green]{success}[/green]"),
            ("Gagal", f"[red]{failed}[/red]" if failed else str(failed)),
            ("Status", status),
        ],
        border_style="green" if failed == 0 else "yellow",
    )


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    if "-h" in raw_argv or "--help" in raw_argv:
        print_help()
        return 0

    args = parse_args(argv)

    if args.workers < 1:
        print_error("--workers harus minimal 1")
        return 2

    if args.interactive:
        return run_interactive(args)

    urls = read_urls(args)
    if not urls:
        if sys.stdin.isatty():
            return run_interactive(args)
        print_error("Tidak ada URL. Berikan URL langsung, --file, stdin '-', atau --interactive.")
        return 2

    options = DownloadOptions(
        output_dir=args.output.expanduser(),
        audio_only=args.audio_only,
        format_selector=args.format_selector,
        archive_file=args.archive.expanduser() if args.archive else None,
        retries=args.retries,
        dry_run=args.dry_run,
    )
    return run_downloads(
        urls=urls,
        options=options,
        allow_playlist=args.playlist,
        workers=args.workers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
