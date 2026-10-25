"""Quick command runner for SigmaOS-quickshell (inspired by omarchy quickshell).

Principles: least astonishment (direct exec by default -- shell is an explicit
opt-in), plan/execute separation (argv plans are pure; only the thin executor
and history file writes touch the system, and self_test uses tempfile only),
fail-fast validation of commands, aliases and limits, deterministic ordering.
"""
import argparse, json, os, re, shlex, subprocess, sys

ENGINE = {
    "name": "sigma-quick",
    "summary": "Quick command runner: run plans, history, aliases, script index",
    "language": "python",
    "verbs": ["run-plan", "history", "alias", "scripts"],
    "principles": ["Separation of Concerns", "Least Astonishment",
                   "Defensive Programming", "Fail-Fast", "KISS",
                   "Deterministic Testing"],
}

cli_doc = """\
$ sigma-quick run-plan "ls -la" --cwd /tmp
ls -la
$ sigma-quick run-plan "ls | wc -l" --shell
/bin/sh -c 'ls | wc -l'
$ sigma-quick history ~/.local/state/sigma-quick/history --record "git status"
$ sigma-quick alias ~/.config/sigma-quick/aliases --add gs='git status'
$ sigma-quick scripts ~/.local/share/sigma-quick/scripts
backup :: backup the home directory
"""

_ALIAS_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALIAS_LINE_RE = re.compile(r"^alias\s+([A-Za-z_][A-Za-z0-9_-]*)=(.+)$")


class QuickError(ValueError):
    pass


def _check_cmd(command):
    if not isinstance(command, str) or not command.strip():
        raise QuickError("empty command")
    if "\x00" in command or "\n" in command or "\r" in command:
        raise QuickError("command must be a single line without NUL bytes")
    return command


# --------------------------------------------------------------------------- #
#  Run planning (pure) + thin executor
# --------------------------------------------------------------------------- #
def plan_run(command, shell=False, timeout=30, cwd=None, env=None):
    """Build the argv that runs `command`. Direct exec unless shell=True."""
    cmd = _check_cmd(command)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise QuickError(f"timeout must be > 0, got {timeout!r}")
    if shell:
        argv = ["/bin/sh", "-c", cmd]
    else:
        try:
            argv = shlex.split(cmd)
        except ValueError as e:
            raise QuickError(f"cannot parse command: {e}") from e
        if not argv:
            raise QuickError("empty command after parsing")
    if cwd is not None and (not isinstance(cwd, str) or not cwd.strip()
                            or "\x00" in cwd or "\n" in cwd):
        raise QuickError(f"bad cwd: {cwd!r}")
    clean_env = {}
    if env is not None:
        if not isinstance(env, dict):
            raise QuickError("env must be a dict")
        for k, v in env.items():
            if not isinstance(k, str) or not _ENV_KEY_RE.match(k):
                raise QuickError(f"bad env var name: {k!r}")
            if not isinstance(v, str) or "\x00" in v:
                raise QuickError(f"bad env value for {k}")
            clean_env[k] = v
    return {"argv": argv, "timeout": timeout, "cwd": cwd, "env": clean_env,
            "shell": bool(shell)}


def execute(plan):
    """THIN side-effecting layer: run the planned command. Never self-tested."""
    return subprocess.run(plan["argv"], cwd=plan.get("cwd"),
                          env=plan.get("env") or None,
                          capture_output=True, text=True,
                          timeout=plan["timeout"])


# --------------------------------------------------------------------------- #
#  History (filesystem; self_test uses tempfile only)
# --------------------------------------------------------------------------- #
def load_history(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [line.rstrip("\n") for line in fh if line.strip()]


def record(command, path, limit=200):
    """Append a command, dedupe consecutive repeats, trim to `limit`."""
    cmd = _check_cmd(command)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise QuickError(f"limit must be a positive integer, got {limit!r}")
    entries = load_history(path)
    if entries and entries[-1] == cmd:
        return entries  # consecutive duplicate: idempotent no-op
    entries = (entries + [cmd])[-limit:]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(e + "\n" for e in entries))
    return entries


# --------------------------------------------------------------------------- #
#  Aliases (pure)
# --------------------------------------------------------------------------- #
def add_alias(aliases, name, command):
    if not isinstance(aliases, dict):
        raise QuickError("aliases must be a dict")
    if not isinstance(name, str) or not _ALIAS_NAME_RE.match(name):
        raise QuickError(f"bad alias name: {name!r}")
    cmd = _check_cmd(command)
    if name in aliases and aliases[name] != cmd:
        raise QuickError(
            f"conflicting alias {name}: {aliases[name]!r} vs {cmd!r}")
    out = dict(aliases)
    out[name] = cmd
    return out


def render_alias_block(aliases):
    lines = ["# sigma-quick aliases"]
    for name in sorted(aliases):
        lines.append(f"alias {name}={shlex.quote(aliases[name])}")
    return "\n".join(lines) + "\n"


def load_aliases(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    aliases = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = _ALIAS_LINE_RE.match(s)
        if not m:
            raise QuickError(f"not an alias line: {s!r}")
        value = m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        aliases = add_alias(aliases, m.group(1), value)
    return aliases


# --------------------------------------------------------------------------- #
#  Script index (read-only filesystem; self_test uses tempfile only)
# --------------------------------------------------------------------------- #
def index_scripts(directory):
    """Sorted index of `*.sh` scripts with optional `#: description` header."""
    if not isinstance(directory, str) or not directory.strip():
        raise QuickError("empty scripts directory")
    if not os.path.isdir(directory):
        raise QuickError(f"no such directory: {directory}")
    out = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".sh"):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        desc = ""
        with open(path, "r", encoding="utf-8") as fh:
            head = [fh.readline() for _ in range(3)]   # shebang + #: header
        for line in head:
            if line.startswith("#:"):
                desc = line[2:].strip()
                break
        out.append({"name": name[:-3], "file": name, "path": path,
                    "desc": desc})
    return out


def render_menu(scripts):
    """rofi/dmenu-style menu lines."""
    return "\n".join(f"{s['name']} :: {s['desc'] or s['file']}"
                     for s in scripts)


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("run-plan", help="build the argv for a command")
    rp.add_argument("command")
    rp.add_argument("--shell", action="store_true", help="run via /bin/sh -c")
    rp.add_argument("--timeout", type=float, default=30)
    rp.add_argument("--cwd", default=None)
    hi = sub.add_parser("history", help="show or record history entries")
    hi.add_argument("file")
    hi.add_argument("--record", default=None, metavar="CMD")
    hi.add_argument("--limit", type=int, default=200)
    al = sub.add_parser("alias", help="list or add aliases")
    al.add_argument("file")
    al.add_argument("--add", default=None, metavar="NAME=VALUE")
    sc = sub.add_parser("scripts", help="index a scripts directory")
    sc.add_argument("directory")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "run-plan":
            plan = plan_run(args.command, shell=args.shell,
                            timeout=args.timeout, cwd=args.cwd)
            print(shlex.join(plan["argv"]))
            bits = [f"timeout={plan['timeout']}"]
            if plan["cwd"]:
                bits.append(f"cwd={plan['cwd']}")
            print("# " + " ".join(bits))
        elif args.cmd == "history":
            entries = (record(args.record, args.file, args.limit)
                       if args.record else load_history(args.file))
            for e in entries:
                print(e)
        elif args.cmd == "alias":
            aliases = load_aliases(args.file)
            if args.add:
                if "=" not in args.add:
                    raise QuickError(f"--add wants NAME=VALUE: {args.add!r}")
                name, value = args.add.split("=", 1)
                aliases = add_alias(aliases, name, value)
            sys.stdout.write(render_alias_block(aliases))
        elif args.cmd == "scripts":
            print(render_menu(index_scripts(args.directory)))
        return 0
    except (QuickError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    import tempfile

    # --- run plans (pure) ---------------------------------------------------
    p = plan_run("ls -la /tmp")
    assert p["argv"] == ["ls", "-la", "/tmp"], p["argv"]
    assert p["shell"] is False and p["timeout"] == 30 and p["env"] == {}
    p = plan_run("ls -l 'a b'")
    assert p["argv"] == ["ls", "-l", "a b"], p["argv"]
    p = plan_run("ls | wc -l", shell=True, cwd="/tmp", env={"LANG": "C"})
    assert p["argv"] == ["/bin/sh", "-c", "ls | wc -l"], p["argv"]
    assert p["cwd"] == "/tmp" and p["env"] == {"LANG": "C"}
    assert plan_run("ls; rm -rf /")["argv"] == ["ls;", "rm", "-rf", "/"]  # no shell!
    for bad_call in ((plan_run, ("",)),
                     (plan_run, ("   ")),
                     (plan_run, ("a\x00b",)),
                     (plan_run, ("ls\nps",)),
                     (plan_run, ("ls", False, 0)),
                     (plan_run, ("ls", False, -1)),
                     (plan_run, ("ls", False, 30, "bad\ncwd")),
                     (plan_run, ("ls", False, 30, None, {"1BAD": "x"})),
                     (plan_run, ("ls", False, 30, None, {"LANG": 5})),
                     (plan_run, ("'unterminated",))):
        try:
            bad_call[0](*bad_call[1])
        except QuickError:
            pass
        else:
            raise AssertionError(f"should have rejected: {bad_call}")
    assert plan_run("ls") == plan_run("ls")  # deterministic

    # --- history (tempfile only) -------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        hfile = os.path.join(d, "history")
        assert load_history(hfile) == []                # missing file -> empty
        assert record("git status", hfile) == ["git status"]
        assert record("git status", hfile) == ["git status"]  # consecutive dedupe
        assert record("ls -la", hfile) == ["git status", "ls -la"]
        assert load_history(hfile) == ["git status", "ls -la"]
        assert record("pwd", hfile, limit=2) == ["ls -la", "pwd"]
        assert load_history(hfile) == ["ls -la", "pwd"]   # trimmed on disk
        with open(hfile, "r", encoding="utf-8") as fh:
            assert fh.read() == "ls -la\npwd\n"
        for bad_call in ((record, ("", hfile)), (record, ("x\x00y", hfile)),
                         (record, ("pwd", hfile, 0)), (record, ("pwd", hfile, -5))):
            try:
                bad_call[0](*bad_call[1])
            except QuickError:
                pass
            else:
                raise AssertionError(f"should have rejected: {bad_call}")

    # --- aliases (pure) -----------------------------------------------------
    a = add_alias({}, "gs", "git status")
    assert a == {"gs": "git status"}
    assert add_alias(a, "gs", "git status") == a          # idempotent
    for bad_call in ((add_alias, (a, "gs", "git stash")),   # conflict
                     (add_alias, (a, "rm -rf", "x")),       # bad name
                     (add_alias, (a, "1st", "x")),
                     (add_alias, (a, "ok", "")),
                     (add_alias, (a, "ok", "multi\nline")),
                     (add_alias, ("not a dict", "k", "v"))):
        try:
            bad_call[0](*bad_call[1])
        except QuickError:
            pass
        else:
            raise AssertionError(f"should have rejected: {bad_call}")
    full = add_alias(add_alias({}, "ll", "ls -lah"), "gs", "git status")
    block = render_alias_block(full)
    assert block == ("# sigma-quick aliases\nalias gs='git status'\n"
                     "alias ll='ls -lah'\n"), block
    assert block == render_alias_block(dict(reversed(list(full.items()))))  # sorted

    # --- script index (tempfile only) --------------------------------------
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "b-backup.sh"), "w") as fh:
            fh.write("#!/bin/sh\n# no description line\ntime\n")
        with open(os.path.join(d, "a-backup.sh"), "w") as fh:
            fh.write("#!/bin/sh\n#: backup the home directory\ntar czf /tmp/h.tgz ~\n")
        with open(os.path.join(d, "notes.txt"), "w") as fh:
            fh.write("#: ignored, not a script\n")
        os.mkdir(os.path.join(d, "sub.sh"))              # directory: skipped
        idx = index_scripts(d)
        assert [s["name"] for s in idx] == ["a-backup", "b-backup"], idx
        assert idx[0]["desc"] == "backup the home directory"
        assert idx[1]["desc"] == ""                        # no #: header
        assert idx[0]["path"].endswith("a-backup.sh")
        menu = render_menu(idx)
        assert menu == ("a-backup :: backup the home directory\n"
                        "b-backup :: b-backup.sh"), menu
        try:
            index_scripts(os.path.join(d, "missing"))
        except QuickError:
            pass
        else:
            raise AssertionError("missing dir not rejected")
        try:
            index_scripts("")
        except QuickError:
            pass
        else:
            raise AssertionError("empty dir not rejected")

    # --- alias file round-trip (tempfile only) ------------------------------
    with tempfile.TemporaryDirectory() as d:
        afile = os.path.join(d, "aliases")
        assert load_aliases(afile) == {}                    # missing -> empty
        with open(afile, "w", encoding="utf-8") as fh:
            fh.write(render_alias_block(full))
        assert load_aliases(afile) == full
        with open(afile, "w", encoding="utf-8") as fh:
            fh.write("this is not an alias\n")
        try:
            load_aliases(afile)
        except QuickError:
            pass
        else:
            raise AssertionError("garbage alias file not rejected")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
