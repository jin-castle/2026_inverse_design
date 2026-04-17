#!/bin/bash
for res in 10 20 30 40; do
    echo -n "res=$res ... "
    t_start=$(date +%s%N)
    python /tmp/res_sweep_v2.py $res
    t_end=$(date +%s%N)
    elapsed=$(( (t_end - t_start) / 1000000 ))
    echo "  => ${elapsed}ms"
    cat /tmp/res_sweep_${res}.json
    echo ""
done
echo "=== 결과 ===" 
for res in 10 20 30 40; do
    echo -n "res=$res: "
    cat /tmp/res_sweep_${res}.json
done
