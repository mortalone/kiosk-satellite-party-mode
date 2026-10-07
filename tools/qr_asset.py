"""Embed the approved QR illustration in DEX; no runtime file/network dependency."""
import base64
from pathlib import Path

def generate(root, output):
    data=base64.b64encode((root/'artwork/guest-speaker.png').read_bytes()).decode('ascii')
    output.mkdir(parents=True,exist_ok=True)
    file=output/'PartyQrIllustration.java'
    chunks=[data[i:i+12000] for i in range(0,len(data),12000)]
    file.write_text('package me.jxl.kiosk.plugins.partymode;\nfinal class PartyQrIllustration {\nstatic String data() {\nStringBuilder b = new StringBuilder();\n'+''.join('b.append("'+chunk+'");\n' for chunk in chunks)+'return b.toString();\n}\n}\n')
    return file
