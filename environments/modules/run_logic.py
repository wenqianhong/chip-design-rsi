#!/usr/bin/env python3
"""Independent module acceptance in Linux; no model or benchmark optimization."""
import hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
root=Path('/home/wenqianhong.guest/chipbench-modules')
out=root/'results';out.mkdir(exist_ok=True)
results=[]
def check(name,args,cwd,timeout=300,expect=0,contains=None):
 log=out/(name+'.log');start=time.monotonic();status='failed';code=None
 try:
  with log.open('w') as f:
   proc=subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  code=proc.returncode;output=log.read_text(errors='replace')
  ok=(code==0 if expect==0 else code!=0) and (contains is None or contains in output)
  status='passed' if ok else 'failed'
 except subprocess.TimeoutExpired:status='timeout'
 row=dict(name=name,status=status,exit_code=code,expected_exit='zero' if expect==0 else 'nonzero',required_text=contains,elapsed_seconds=round(time.monotonic()-start,3),command=args,log=log.name)
 results.append(row);(out/'logic-results.json').write_text(json.dumps(results,indent=2));print(json.dumps(row),flush=True)
 return status=='passed'
pico=root/'picorv32';fixtures=root/'fixtures'
check('versions',['bash','-c','iverilog -V; verilator --version; yosys -V; z3 --version; riscv64-unknown-elf-gcc --version; klayout -v'],root)
# New compiler ISA spelling: zicsr is used by the upstream firmware counters.
makefile=pico/'Makefile'
text=makefile.read_text()
for arch in ['rv32im$(subst C,c,$(COMPRESSED_ISA))','rv32i$(subst C,c,$(COMPRESSED_ISA))']:
 text=text.replace('-march='+arch+' ', '-march='+arch+'_zicsr ')
makefile.write_text(text)
patch=subprocess.run(['git','diff','--','Makefile'],cwd=pico,capture_output=True,text=True).stdout
(out/'compiler-compatibility.patch').write_text(patch)
flags=['TOOLCHAIN_PREFIX=riscv64-unknown-elf-','COMPRESSED_ISA=C']
check('pico-iverilog',['make','test',*flags],pico,timeout=600,contains='ALL TESTS PASSED.')
check('pico-verilator',['make','test_verilator',*flags],pico,timeout=600,contains='ALL TESTS PASSED.')
check('counter-compile',['iverilog','-g2012','-o',str(out/'counter.vvp'),'counter.sv','counter_tb.sv'],fixtures)
check('counter-simulation',['vvp',str(out/'counter.vvp')],fixtures,contains='COUNTER_PASS checks=3')
bad=(fixtures/'counter.sv').read_text().replace('count + 1','count + 2')
(fixtures/'counter_bad.sv').write_text(bad)
check('wrong-logic-compile',['iverilog','-g2012','-o',str(out/'bad.vvp'),'counter_bad.sv','counter_tb.sv'],fixtures)
check('wrong-logic-detected',['vvp',str(out/'bad.vvp')],fixtures,expect=1,contains='counter wrap mismatch')
(fixtures/'syntax_bad.v').write_text('module broken(input clk); not valid syntax! endmodule\n')
check('syntax-error-detected',['iverilog','-o',str(out/'syntax.vvp'),'syntax_bad.v'],fixtures,expect=1,contains='syntax error')
formal='read_verilog -formal -sv counter.sv; prep -top counter; flatten; sat -seq 4 -tempinduct -prove-asserts -verify -dump_vcd '+str(out/'formal.vcd')
check('counter-induction',['yosys','-p',formal],fixtures,contains='SUCCESS')
check('formal-bug-detected',['yosys','-p',formal.replace('counter.sv','counter_bad.sv').replace('formal.vcd','counterexample.vcd')],fixtures,expect=1,contains='proof did fail')
check('counter-synthesis',['yosys','-p','read_verilog counter.sv; synth -top counter; check -assert; stat; write_verilog -noattr '+str(out/'counter_netlist.v')],fixtures,contains='Found and reported 0 problems')
check('netlist-compile',['iverilog','-g2012','-o',str(out/'netlist.vvp'),str(out/'counter_netlist.v'),'counter_tb.sv'],fixtures)
check('netlist-simulation',['vvp',str(out/'netlist.vvp')],fixtures,contains='COUNTER_PASS checks=3')
check('pico-synthesis',['make','synth.v'],pico,timeout=600)
check('pico-gate-simulation',['make','test_synth',*flags],pico,timeout=600,contains='ALL TESTS PASSED.')
