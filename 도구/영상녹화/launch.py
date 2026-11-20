import subprocess, os
HERE = os.path.dirname(os.path.abspath(__file__))
subprocess.Popen([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--remote-debugging-port=9333",
  "--user-data-dir=" + os.path.join(HERE, "profile"), "--no-first-run", "--no-default-browser-check",
  "--window-size=1460,1040", "--window-position=40,20", "https://farmfood.adminplus.co.kr/partner-app/#/product"])
