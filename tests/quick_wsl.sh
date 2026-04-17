#!/bin/bash
# WSL2에서 실행 - 로컬 KB API 접근
KB="http://localhost:8765"

declare -A CASES
declare -a CASE_IDS=(
    "C2_PML_center"
    "C4_DPW_kwarg"
    "C5_flux_minus"
    "C6_eig_band"
    "ML2_U_SUM"
    "ML3_Source_kw"
    "ML1_cyl_m0"
)
declare -A QUERIES=(
    ["C2_PML_center"]="TypeError PML unexpected keyword argument center"
    ["C4_DPW_kwarg"]="DiffractedPlanewave unexpected keyword argument"
    ["C5_flux_minus"]="T+R greater than 2.0 energy conservation load_minus_flux_data"
    ["C6_eig_band"]="eig_band 0 eigenmode MEEP 1-based"
    ["ML2_U_SUM"]="MaterialGrid U_SUM ValueError MEEP 1.31"
    ["ML3_Source_kw"]="mp.Source AttributeError Vector3 center keyword"
    ["ML1_cyl_m0"]="cylindrical zone plate m=0 no focusing"
)

passed=0
total=${#CASE_IDS[@]}

echo "=== meep-kb Quick Regression (WSL2) ==="
for cid in "${CASE_IDS[@]}"; do
    query="${QUERIES[$cid]}"
    response=$(curl -s -m 10 -X POST "$KB/api/diagnose" \
        -H "Content-Type: application/json" \
        -d "{\"error\": \"$query\", \"n\": 3}" 2>/dev/null)
    
    if [ -z "$response" ]; then
        echo "[TIMEOUT] $cid"
        continue
    fi
    
    n_sug=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('suggestions',[])) )" 2>/dev/null)
    title=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); s=d.get('suggestions',[]); print(s[0]['title'][:60] if s else 'NO RESULT')" 2>/dev/null)
    
    if [ "$n_sug" -gt "0" ] 2>/dev/null; then
        echo "[PASS] $cid | $n_sug results | $title"
        ((passed++))
    else
        echo "[FAIL] $cid | NO RESULT"
    fi
done

echo ""
echo "=== $passed/$total PASS ==="
