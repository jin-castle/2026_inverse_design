"""이미지 크기로 하얀/빈 이미지 감지 + 실제 픽셀 확인."""
from pathlib import Path
import struct, zlib

def is_white_png(path: Path) -> bool:
    """PNG 파일이 단색(흰색/거의 흰색)인지 확인."""
    try:
        data = path.read_bytes()
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            return False
        # IDAT chunk 찾기
        pos = 8
        while pos < len(data) - 12:
            length = struct.unpack('>I', data[pos:pos+4])[0]
            chunk_type = data[pos+4:pos+8]
            if chunk_type == b'IDAT':
                compressed = data[pos+8:pos+8+length]
                raw = zlib.decompress(compressed)
                # 첫 100바이트 샘플
                sample = raw[:300]
                non_white = sum(1 for b in sample if b not in (0, 255, 0xfe, 0xfd))
                return non_white < 5  # 거의 흰색/검정
            pos += length + 12
        return False
    except:
        return False

results_dir = Path("db/results")
pngs = sorted(results_dir.glob("concept_*.png"))

print(f"총 {len(pngs)}개 이미지\n")
print(f"{'파일명':<45} {'크기':>8}  {'상태'}")
print("-" * 70)

suspects = []
for p in pngs:
    size = p.stat().st_size
    size_kb = size / 1024
    white = is_white_png(p) if size_kb < 5 else False
    status = "⚠️  WHITE?" if white else ("🔴 tiny" if size_kb < 3 else "✅")
    if white or size_kb < 3:
        suspects.append(p.name)
    print(f"  {p.name:<43} {size_kb:>6.1f}KB  {status}")

print(f"\n⚠️  의심 이미지: {len(suspects)}개")
for s in suspects:
    print(f"  {s}")
