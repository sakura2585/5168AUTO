# -*- mode: python ; coding: utf-8 -*-
# 上傳小幫手「完整打包」尋找 order_note_full.spec；邏輯同 5168AUTO_full.spec

import os
import runpy

runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(SPEC)), "5168AUTO_full.spec"),
    init_globals=globals(),
)
