#!/bin/bash
export ANTHROPIC_API_KEY="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"
cd /mnt/c/Users/user/projects/meep-kb

echo "=========================================="
echo "테스트 1: adjoint 돌리다가 죽었어"
echo "=========================================="
python3 search_agent.py "adjoint 돌리다가 죽었어" --n 3 2>&1 | grep -v -E '(Loading|BertModel|LOAD|UNEXPECTED|Notes:|Materiali)'

echo ""
echo "=========================================="
echo "테스트 2: my simulation blows up"
echo "=========================================="
python3 search_agent.py "my simulation blows up after a few steps" --n 3 2>&1 | grep -v -E '(Loading|BertModel|LOAD|UNEXPECTED|Notes:|Materiali)'

echo ""
echo "=========================================="
echo "테스트 3: adjoint랑 MPI 관계가 뭐야"
echo "=========================================="
python3 search_agent.py "adjoint랑 MPI 관계가 뭐야" --n 3 2>&1 | grep -v -E '(Loading|BertModel|LOAD|UNEXPECTED|Notes:|Materiali)'
