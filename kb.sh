#!/bin/bash
# MEEP-KB 통합 검색 단축 스크립트
# 사용법: ./kb.sh "질문"
#         ./kb.sh "질문" --n 7
#         ./kb.sh "질문" --verbose

export ANTHROPIC_API_KEY="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"
cd /mnt/c/Users/user/projects/meep-kb
python3 search_agent.py "$@" 2>&1 | grep -v -E '(Loading weights|BertModel|LOAD REPORT|UNEXPECTED|Notes:|Materializ|Warning: You are sending)'
