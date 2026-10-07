"""Decode the actual Java renderer output, including long dynamic guest capabilities."""
from pathlib import Path
from PIL import Image, ImageFilter
import zxingcpp, io
count=0
for file in sorted(Path('dist/qa/qr-art').glob('*.png')):
    im=Image.open(file).convert('RGBA');expected=file.with_suffix('.txt').read_text()
    for color in ['#090e17','#151b26','#253044']:
        for size in [650,420,320,240]:
            canvas=Image.new('RGBA',(size,size),color)
            canvas.alpha_composite(im.resize((size,size),Image.Resampling.LANCZOS))
            found=zxingcpp.read_barcodes(canvas.convert('RGB'))
            assert any(code.text==expected for code in found),(file.name,color,size)
            count+=1
    canvas=Image.new('RGBA',(420,420),'#090e17');canvas.alpha_composite(im.resize((420,420),Image.Resampling.LANCZOS))
    stream=io.BytesIO();canvas.convert('RGB').filter(ImageFilter.GaussianBlur(.65)).save(stream,format='JPEG',quality=70)
    assert any(code.text==expected for code in zxingcpp.read_barcodes(Image.open(io.BytesIO(stream.getvalue())))),file.name
    count+=1
assert count==65,count
print(f'{count} dynamic artistic QR decode checks passed (phone verification remains separate).')
