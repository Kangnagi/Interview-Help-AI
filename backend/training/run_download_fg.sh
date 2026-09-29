#!/bin/bash
# 이 스크립트가 끝날 때까지 WSL 세션을 붙잡아 다운로드를 유지한다 (세션 종료 시 WSL이 프로세스를 죽이므로).
# 완료·실패 시에만 한 줄 출력한다. 이미 받은 부분은 이어받는다.
cd ~/llama-train
HF_HUB_DISABLE_XET=1 ~/venvs/llama-finetune/bin/python download_teacher.py > download.log 2>&1
code=$?
grep -q DOWNLOAD_DONE download.log && echo "DOWNLOAD_DONE" || echo "DOWNLOAD_FAILED (exit $code): $(tail -c 300 download.log)"
