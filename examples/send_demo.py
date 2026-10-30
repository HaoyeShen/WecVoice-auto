"""Minimal end-to-end example.

Before running:

1. Install VB-CABLE and reboot.
2. Set ``CABLE Output`` as the default recording device (or let this library
   switch it automatically).
3. Log in to WeChat 4.1.9+ and open the target conversation.
4. ``wecvoice doctor`` should report all green.

Then run::

    python examples/send_demo.py "老师早上好！"
"""

from __future__ import annotations

import sys

from wecvoice_auto import VoiceSender


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else "老师早上好！阿洛娜今天也会加油的。"
    sender = VoiceSender()
    result = sender.send(text, chat="文件传输助手", voice="arona")
    print(result.to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
