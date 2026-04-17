#!/bin/bash
for f in /tmp/l2_n*.log; do
    r=$(grep -m1 Result "$f" 2>/dev/null)
    if [ -n "$r" ]; then
        echo "$f: $r"
    fi
done
