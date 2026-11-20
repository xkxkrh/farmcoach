"""배포용 압축파일 만들기:  py 배포/make_zip.py  →  dist/팜코치_런처.zip
압축 안에는 [팜코치_런처] 폴더 하나와 그 안에 3개 파일이 들어갑니다."""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "배포")
OUT_DIR = os.path.join(ROOT, "dist")
OUT = os.path.join(OUT_DIR, "팜코치_런처.zip")
FILES = [
    (os.path.join(HERE, "팜코치_런처_실행.bat"), "팜코치_런처/팜코치_런처_실행.bat"),
    (os.path.join(ROOT, "launcher.pyw"), "팜코치_런처/launcher.pyw"),
    (os.path.join(HERE, "실행전_가이드라인.txt"), "팜코치_런처/실행전_가이드라인.txt"),
]

os.makedirs(OUT_DIR, exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:  # 한글 파일 이름은 UTF-8 표시로 저장됨
    for src, arc in FILES:
        z.write(src, arc)
print(OUT, os.path.getsize(OUT), "bytes")

# 메신저로는 .bat 이 든 압축파일을 못 보내서, 사이트에도 올려 '내려받기 링크'로 전달함
# 주소: https://xkxkrh.github.io/farmcoach/download/farmcoach-launcher.zip
import shutil
WEB = os.path.join(ROOT, "docs", "download", "farmcoach-launcher.zip")
os.makedirs(os.path.dirname(WEB), exist_ok=True)
shutil.copyfile(OUT, WEB)
print(WEB)
