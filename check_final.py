import sqlite3, json

conn = sqlite3.connect('/app/db/knowledge.db')
cur = conn.cursor()

# 오늘 처리한 IDs
target_ids = [333, 341, 353, 375, 381, 389, 400, 505, 513, 526, 528, 539, 548, 562, 573, 592]
ids_str = ','.join(map(str, target_ids))
cur.execute(f"SELECT id, title, result_status, result_images FROM examples WHERE id IN ({ids_str}) ORDER BY id")
print("=== 처리 대상 상태 ===")
for row in cur.fetchall():
    imgs = row[3]
    img_list = json.loads(imgs) if imgs and imgs not in ('[]', None) else []
    img_count = len(img_list)
    status = row[2] if row[2] else 'NULL'
    marker = '✅' if img_count > 0 else ('🔲' if status == 'success' else '❌')
    print(f"  {marker} id={row[0]} [{status}] 이미지:{img_count} | {str(row[1])[:45]}")

# 전체 현황
cur.execute("SELECT result_status, COUNT(*) FROM examples GROUP BY result_status")
print("\n=== 전체 현황 ===")
for row in cur.fetchall():
    print(f"  {row[0] or 'NULL'}: {row[1]}")

# 이미지 있는 성공 건수
cur.execute("SELECT COUNT(*) FROM examples WHERE result_status='success' AND result_images NOT IN ('[]', 'null', '') AND result_images IS NOT NULL")
print(f"\n이미지 포함 success: {cur.fetchone()[0]}개")
conn.close()
