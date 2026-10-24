"""Native Windows path picker; returns a path only, never reads/uploads a file."""
import argparse
import json
import sys

def choose(kind):
    import tkinter as tk
    from tkinter import filedialog
    root=tk.Tk();root.withdraw();root.attributes('-topmost',True)
    try:
        if kind=='directory':return filedialog.askdirectory(parent=root,title='nopilot — Chọn thư mục dự án',mustexist=True)
        return filedialog.askopenfilename(parent=root,title='nopilot — Chọn đường dẫn file',filetypes=[('All files','*.*')])
    finally:root.destroy()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=['file','directory'])
    args=parser.parse_args();sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps({'path':choose(args.kind)},ensure_ascii=False))
