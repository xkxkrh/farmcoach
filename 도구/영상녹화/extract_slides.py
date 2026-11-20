r"""발주 가이드 PDF(엑셀에서 'PDF로 인쇄'한 것)에서 화면 사진을 꺼내 slides/ 폴더에 저장.
Usage: py extract_slides.py "C:\...\팜코치 발주 가이드.pdf"
파일 이름은 p01_obj4.jpg 처럼 '순서_PDF내부번호' 이고, record.py 의 slide(...) 가 이 이름을 씁니다.
PDF를 새로 만들면 번호가 바뀔 수 있으니, 실행 후 slides 폴더 이름을 보고 record.py 의 이름을 맞춰 주세요."""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "slides"); os.makedirs(OUT, exist_ok=True)
d = open(sys.argv[1], "rb").read()
i = 0
for m in re.finditer(rb"(\d+) 0 obj\s*<<(.*?)>>\s*stream\r?\n", d, re.S):
    if b"DCTDecode" not in m.group(2):
        continue
    L = int(re.search(rb"/Length (\d+)", m.group(2)).group(1))
    i += 1
    open(os.path.join(OUT, "p%02d_obj%s.jpg" % (i, m.group(1).decode())), "wb").write(d[m.end():m.end() + L])
print(i, "장 저장:", OUT)
