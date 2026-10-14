"""configs/secrets/lab.env 를 읽는다. 실값은 저장소에 두지 않는다.

환경변수로 덮어쓸 수 있다(예: UE1_KI=... python3 tools/verify.py).
파일이 없으면 무엇을 해야 하는지 알려 주고 멈춘다.
"""
import os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / "configs" / "secrets" / "lab.env"


def load():
    vals = {}
    if PATH.is_file():
        for line in PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    vals.update({k: v for k, v in os.environ.items() if k in vals or k.startswith("UE")})
    return vals


def need(*keys):
    """필요한 값만 꺼낸다. 없으면 이유를 적고 종료."""
    vals = load()
    missing = [k for k in keys if not vals.get(k) or vals[k].startswith("<")]
    if missing:
        sys.exit(
            f"비밀값이 없다: {', '.join(missing)}\n"
            f"  {PATH} 를 만들고 채울 것.\n"
            f"  cp configs/secrets/lab.env.example configs/secrets/lab.env && chmod 600 ...")
    return [vals[k] for k in keys]
