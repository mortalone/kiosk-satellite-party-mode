"""Run the production detail allocator without Android; guard reuse and Eco compatibility."""
from pathlib import Path
import subprocess, tempfile
source=Path('src/me/jxl/kiosk/plugins/partymode/PartyEffects.java').read_text()
methods=source[source.index('    void setEconomy('):source.index('    boolean fresh()')]
java='''public class DetailTest {
 float[] target, levels, waveform, cosines, sines; int particleCount, ringCount;
'''+methods+'''
 public static void main(String[] args){
 DetailTest d=new DetailTest();d.setEconomy(true);
 if(d.target.length!=32||d.waveform.length!=64||d.particleCount!=28||d.ringCount!=7)throw new AssertionError("Legacy Eco must survive upgrades");
 d.setDetail(3);if(d.target.length!=64||d.waveform.length!=128||d.particleCount!=80||d.ringCount!=16)throw new AssertionError("High budget");
 float[] old=d.levels;old[0]=.75f;d.setDetail(3);
 if(d.levels!=old||d.levels[0]!=.75f)throw new AssertionError("Repeated selection must preserve smoothing buffers");
 d.setDetail(1);if(d.target.length!=24||d.waveform.length!=48)throw new AssertionError("Low budget");
 d.setEconomy(false);if(d.target.length!=48||d.waveform.length!=96)throw new AssertionError("Restore normal");
 for(int i=0;i<d.cosines.length;i++)if(Math.abs(d.cosines[i]*d.cosines[i]+d.sines[i]*d.sines[i]-1)>1e-5)throw new AssertionError("Radial geometry");
 System.out.println("Detail allocator passed");
 }}'''
with tempfile.TemporaryDirectory() as temp:
 p=Path(temp)/'DetailTest.java';p.write_text(java)
 subprocess.run(['javac','--release','8',str(p)],check=True)
 subprocess.run(['java','-cp',temp,'DetailTest'],check=True)
