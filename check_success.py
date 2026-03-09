import sqlite3, json

conn = sqlite3.connect('/app/db/knowledge.db')
cur = conn.cursor()

# success 예제 중 이미지 있는 것 확인
cur.execute("SELECT id, title, result_images, result_stdout FROM examples WHERE result_status='success' ORDER BY id")
print('=== success 예제 (이미지 포함 여부) ===')
no_img = []
has_img = []
for row in cur.fetchall():
    imgs = row[2]
    img_list = json.loads(imgs) if imgs and imgs != '[]' else []
    img_count = len(img_list)
    if img_count > 0:
        has_img.append(row[0])
    else:
        no_img.append(row[0])

print(f'이미지 있음: {len(has_img)}개 — {has_img[:20]}')
print(f'이미지 없음: {len(no_img)}개 — {no_img[:20]}')

# results 디렉토리 파일 목록
import os
results_dir = '/app/db/results'
if os.path.exists(results_dir):
    files = os.listdir(results_dir)
    print(f'\n/app/db/results/ 파일 수: {len(files)}')
    print('최근 파일:', sorted(files)[-10:] if files else '없음')
conn.close()
