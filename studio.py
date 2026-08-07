#!/usr/bin/env python3
"""
Studio — công cụ tạo coloring book.

Cách dùng thường ngày — một công thức, một lệnh, chạy hai lần:

    python studio.py make dai-duong-ky-thu --init   # tạo books/<slug>.yaml
    python studio.py make dai-duong-ky-thu          # lần 1: sinh ảnh
    #   ... mở raw/ xoá ảnh xấu, bấm giờ ...
    python studio.py make dai-duong-ky-thu --minutes 95   # lần 2: dựng sách

Các lệnh lẻ, khi cần làm từng bước:

    python studio.py doctor
    python studio.py subjects "Giáng sinh" --count 24
    python studio.py generate "Giáng sinh" --theme giang-sinh --count 40
    python studio.py approve dai-duong-ky-thu --minutes 95
    python studio.py build dai-duong-ky-thu
    python studio.py cover dai-duong-ky-thu
    python studio.py measure dai-duong-ky-thu --vs ban-thu-nghiem

Quy trình 5 bước của roadmap, Phase 1 phủ bước ① ② ③:

    ① TẠO  →  ② DUYỆT  →  ③ DỰNG  →  ④ ĐĂNG  →  ⑤ BÁN
   generate   xoá tay +   build +     (chưa làm)  (chưa làm)
              approve      cover

`cover` phải chạy SAU `build`: độ dày gáy tính từ số trang thật của ruột.
"""

from __future__ import annotations

import argparse
import sys

from studio.commands import (approve, build, cover, doctor, generate, make,
                             measure, subjects)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="studio.py",
        description="Công cụ tạo coloring book — Phase 1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<lệnh>")

    doctor.register(subparsers)
    make.register(subparsers)
    subjects.register(subparsers)
    generate.register(subparsers)
    approve.register(subparsers)
    build.register(subparsers)
    cover.register(subparsers)
    measure.register(subparsers)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nĐã dừng.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
