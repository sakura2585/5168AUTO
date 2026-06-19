# -*- mode: python ; coding: utf-8 -*-
# 上傳小幫手 gh_push 預設尋找 order_note.spec；邏輯同 5168AUTO.spec

import os
import runpy

runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(SPEC)), "5168AUTO.spec"),
    init_globals=globals(),
)
